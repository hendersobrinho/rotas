"""Usuários, autenticação e o 'continuar conectado'."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AcaoLog, EntidadeLog, SessaoSalva, Usuario
from app.repository import logs as repo_logs
from app.schemas import DadosUsuario
from app.seguranca import conferir, gerar_hash, gerar_token, hash_token

DIAS_DE_SESSAO = 30


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def listar(sessao: Session, apenas_ativos: bool = False) -> list[Usuario]:
    consulta = select(Usuario)
    if apenas_ativos:
        consulta = consulta.where(Usuario.ativo.is_(True))
    return list(sessao.scalars(consulta.order_by(func.lower(Usuario.nome))))


def obter(sessao: Session, usuario_id: int) -> Usuario | None:
    return sessao.get(Usuario, usuario_id)


def obter_por_login(sessao: Session, login: str) -> Usuario | None:
    consulta = select(Usuario).where(func.lower(Usuario.login) == (login or "").strip().lower())
    return sessao.scalars(consulta).first()


def existe_algum(sessao: Session) -> bool:
    return bool(sessao.scalar(select(func.count(Usuario.id))))


def criar(sessao: Session, dados: DadosUsuario, anotar: bool = True) -> Usuario:
    dados = dados.normalizado()
    _validar(sessao, dados)
    if not dados.senha:
        raise ValueError("Defina uma senha para o usuário.")

    usuario = Usuario(
        nome=dados.nome,
        login=dados.login,
        senha_hash=gerar_hash(dados.senha),
        ativo=dados.ativo,
    )
    sessao.add(usuario)
    sessao.flush()
    if anotar:
        repo_logs.registrar(
            sessao, AcaoLog.CRIACAO, EntidadeLog.USUARIO,
            f"Usuário “{usuario.nome}” ({usuario.login})", usuario.id,
        )
    return usuario


def atualizar(sessao: Session, usuario_id: int, dados: DadosUsuario) -> Usuario:
    usuario = obter(sessao, usuario_id)
    if usuario is None:
        raise ValueError("Usuário não encontrado.")
    dados = dados.normalizado()
    _validar(sessao, dados, ignorar_id=usuario_id)

    if not dados.ativo and usuario.ativo and _ativos_restantes(sessao, usuario_id) == 0:
        raise ValueError("Este é o último usuário ativo — deixe ao menos um.")

    mudou_senha = bool(dados.senha)
    usuario.nome, usuario.login, usuario.ativo = dados.nome, dados.login, dados.ativo
    if mudou_senha:
        usuario.senha_hash = gerar_hash(dados.senha)
        # Trocar a senha derruba os 'continuar conectado' antigos.
        for salva in list(usuario.sessoes):
            sessao.delete(salva)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.ALTERACAO, EntidadeLog.USUARIO,
        f"Usuário “{usuario.nome}”" + (" (senha trocada)" if mudou_senha else ""),
        usuario.id,
    )
    return usuario


def excluir(sessao: Session, usuario_id: int, usuario_logado_id: int | None = None) -> None:
    usuario = obter(sessao, usuario_id)
    if usuario is None:
        raise ValueError("Usuário não encontrado.")
    if usuario_logado_id is not None and usuario_id == usuario_logado_id:
        raise ValueError("Você não pode excluir o usuário com que está conectado.")
    if _ativos_restantes(sessao, usuario_id) == 0:
        raise ValueError("Este é o último usuário ativo — deixe ao menos um.")

    nome, login = usuario.nome, usuario.login
    sessao.delete(usuario)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.EXCLUSAO, EntidadeLog.USUARIO, f"Usuário “{nome}” ({login})"
    )


def autenticar(sessao: Session, login: str, senha: str) -> Usuario:
    """Devolve o usuário ou explica por que não deu."""
    usuario = obter_por_login(sessao, login)
    if usuario is None or not conferir(senha or "", usuario.senha_hash):
        raise ValueError("Usuário ou senha não conferem.")
    if not usuario.ativo:
        raise ValueError("Este usuário está inativo. Procure quem administra o sistema.")

    usuario.ultimo_acesso = _agora()
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.LOGIN, EntidadeLog.SISTEMA, f"Entrou como {usuario.login}",
        usuario.id, usuario_id=usuario.id, usuario_nome=usuario.nome,
    )
    return usuario


def registrar_saida(sessao: Session, usuario: Usuario | None, nome: str) -> None:
    repo_logs.registrar(
        sessao, AcaoLog.LOGOUT, EntidadeLog.SISTEMA, "Saiu do sistema",
        usuario.id if usuario else None,
        usuario_id=usuario.id if usuario else None, usuario_nome=nome,
    )


# ------------------------------------------------------- continuar conectado
def criar_sessao_salva(sessao: Session, usuario: Usuario, maquina: str) -> str:
    """Cria o token que fica no computador; aqui guarda-se só o hash dele."""
    token = gerar_token()
    sessao.add(
        SessaoSalva(
            usuario_id=usuario.id,
            token_hash=hash_token(token),
            maquina=maquina,
            expira_em=_agora() + timedelta(days=DIAS_DE_SESSAO),
        )
    )
    sessao.flush()
    return token


def usuario_do_token(sessao: Session, token: str) -> Usuario | None:
    salva = sessao.scalars(
        select(SessaoSalva).where(SessaoSalva.token_hash == hash_token(token or ""))
    ).first()
    if salva is None:
        return None
    if salva.expira_em <= _agora():
        sessao.delete(salva)
        sessao.flush()
        return None
    if not salva.usuario.ativo:
        return None
    salva.usuario.ultimo_acesso = _agora()
    sessao.flush()
    return salva.usuario


def encerrar_sessao_salva(sessao: Session, token: str) -> None:
    salva = sessao.scalars(
        select(SessaoSalva).where(SessaoSalva.token_hash == hash_token(token or ""))
    ).first()
    if salva is not None:
        sessao.delete(salva)
        sessao.flush()


def limpar_sessoes_expiradas(sessao: Session) -> int:
    expiradas = list(
        sessao.scalars(select(SessaoSalva).where(SessaoSalva.expira_em <= _agora()))
    )
    for salva in expiradas:
        sessao.delete(salva)
    sessao.flush()
    return len(expiradas)


def _ativos_restantes(sessao: Session, ignorar_id: int) -> int:
    consulta = select(func.count(Usuario.id)).where(
        Usuario.ativo.is_(True), Usuario.id != ignorar_id
    )
    return int(sessao.scalar(consulta) or 0)


def _validar(sessao: Session, dados: DadosUsuario, ignorar_id: int | None = None) -> None:
    if not dados.nome:
        raise ValueError("Informe o nome do usuário.")
    if not dados.login:
        raise ValueError("Informe o login.")
    if " " in dados.login:
        raise ValueError("O login não pode ter espaços.")
    if dados.senha and len(dados.senha) < 4:
        raise ValueError("A senha precisa de pelo menos 4 caracteres.")

    consulta = select(Usuario.id).where(func.lower(Usuario.login) == dados.login.lower())
    if ignorar_id is not None:
        consulta = consulta.where(Usuario.id != ignorar_id)
    if sessao.scalars(consulta).first() is not None:
        raise ValueError(f"Já existe um usuário com o login “{dados.login}”.")
