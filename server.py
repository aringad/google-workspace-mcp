"""
MCP Server per Google Workspace Admin
Gestione utenti, gruppi, alias via Admin SDK Directory API.

Autore: Giuliano Delfino / Mediaform s.c.r.l.
"""

import json
import os
import secrets
import string
from typing import Optional, List
from enum import Enum

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator, ConfigDict
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ─────────────────────────────────────────────
# Configurazione
# ─────────────────────────────────────────────

SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    os.path.join(os.path.dirname(__file__), "credentials.json")
)
ADMIN_EMAIL = os.getenv("GOOGLE_ADMIN_EMAIL", "")  # Email admin con delega
CUSTOMER_ID = os.getenv("GOOGLE_CUSTOMER_ID", "my_customer")  # "my_customer" = dominio corrente

SCOPES = [
    "https://www.googleapis.com/auth/admin.directory.user",
    "https://www.googleapis.com/auth/admin.directory.group",
    "https://www.googleapis.com/auth/admin.directory.orgunit",
    "https://www.googleapis.com/auth/admin.directory.user.alias",
]

# ─────────────────────────────────────────────
# Client Google Admin SDK
# ─────────────────────────────────────────────

def get_directory_service():
    """Crea e restituisce il servizio Directory API autenticato."""
    if not ADMIN_EMAIL:
        raise ValueError(
            "GOOGLE_ADMIN_EMAIL non configurato. "
            "Impostalo con l'email dell'admin che ha la delega domain-wide."
        )
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    delegated = credentials.with_subject(ADMIN_EMAIL)
    return build("admin", "directory_v1", credentials=delegated)


def handle_google_error(e: Exception) -> str:
    """Formatta errori Google API in messaggi leggibili."""
    if isinstance(e, HttpError):
        status = e.resp.status
        try:
            detail = json.loads(e.content.decode())
            message = detail.get("error", {}).get("message", str(e))
        except (json.JSONDecodeError, AttributeError):
            message = str(e)

        error_map = {
            400: f"Richiesta non valida: {message}",
            403: f"Permessi insufficienti: {message}. Verifica la delega domain-wide del Service Account.",
            404: f"Risorsa non trovata: {message}",
            409: f"Conflitto: {message} (l'utente/gruppo potrebbe già esistere)",
            429: "Rate limit superato. Riprova tra qualche secondo.",
        }
        return error_map.get(status, f"Errore API Google (HTTP {status}): {message}")
    elif isinstance(e, FileNotFoundError):
        return f"File credenziali non trovato: {SERVICE_ACCOUNT_FILE}. Verifica il path."
    elif isinstance(e, ValueError):
        return f"Errore configurazione: {e}"
    return f"Errore imprevisto: {type(e).__name__}: {e}"


def generate_temp_password(length: int = 16) -> str:
    """Genera una password temporanea sicura."""
    chars = string.ascii_letters + string.digits + "!@#$%&*"
    return ''.join(secrets.choice(chars) for _ in range(length))


def format_user(user: dict) -> str:
    """Formatta un utente in output leggibile."""
    name = user.get("name", {})
    lines = [
        f"📧 **{user.get('primaryEmail', 'N/A')}**",
        f"   Nome: {name.get('fullName', 'N/A')}",
        f"   ID: {user.get('id', 'N/A')}",
        f"   Stato: {'🟢 Attivo' if not user.get('suspended') else '🔴 Sospeso'}",
        f"   Admin: {'Sì' if user.get('isAdmin') else 'No'}",
        f"   Ultimo accesso: {user.get('lastLoginTime', 'Mai')}",
        f"   Creazione: {user.get('creationTime', 'N/A')}",
    ]
    aliases = user.get("aliases", [])
    if aliases:
        lines.append(f"   Alias: {', '.join(aliases)}")
    org = user.get("orgUnitPath", "/")
    if org:
        lines.append(f"   Unità org.: {org}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Server MCP
# ─────────────────────────────────────────────

mcp = FastMCP("google_workspace_mcp")

# =============================================
# TOOL: Lista utenti
# =============================================

class ListUsersInput(BaseModel):
    """Input per la lista utenti."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: Optional[str] = Field(
        default=None,
        description=(
            "Query di ricerca Google Admin (es. 'name:Mario' oppure "
            "'email:mario@dominio.it' oppure 'orgUnitPath=/Vendite'). "
            "Lascia vuoto per tutti gli utenti."
        )
    )
    max_results: Optional[int] = Field(
        default=100, description="Numero massimo di utenti da restituire", ge=1, le=500
    )
    order_by: Optional[str] = Field(
        default="email",
        description="Campo per ordinamento: 'email', 'familyName', 'givenName'"
    )
    show_suspended: Optional[bool] = Field(
        default=True, description="Includi utenti sospesi nei risultati"
    )


@mcp.tool(
    name="gw_list_users",
    annotations={
        "title": "Lista utenti Google Workspace",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def gw_list_users(params: ListUsersInput) -> str:
    """Elenca gli utenti del dominio Google Workspace con ricerca opzionale.

    Supporta query Admin SDK come:
    - name:Mario → cerca per nome
    - email:mario* → cerca per email con wildcard
    - orgUnitPath=/Ufficio → cerca per unità organizzativa
    - isSuspended=true → solo utenti sospesi

    Returns:
        str: Lista formattata degli utenti trovati.
    """
    try:
        service = get_directory_service()
        kwargs = {
            "customer": CUSTOMER_ID,
            "maxResults": params.max_results,
            "orderBy": params.order_by,
        }
        if params.query:
            kwargs["query"] = params.query

        result = service.users().list(**kwargs).execute()
        users = result.get("users", [])

        if not params.show_suspended:
            users = [u for u in users if not u.get("suspended")]

        if not users:
            return "Nessun utente trovato con i criteri specificati."

        output = [f"## Utenti trovati: {len(users)}\n"]
        for user in users:
            output.append(format_user(user))
            output.append("---")

        return "\n".join(output)

    except Exception as e:
        return handle_google_error(e)


# =============================================
# TOOL: Dettaglio utente
# =============================================

class GetUserInput(BaseModel):
    """Input per dettaglio utente."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_key: str = Field(
        ...,
        description="Email o ID dell'utente (es. 'mario.rossi@dominio.it')",
        min_length=1,
    )


@mcp.tool(
    name="gw_get_user",
    annotations={
        "title": "Dettaglio utente Google Workspace",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def gw_get_user(params: GetUserInput) -> str:
    """Recupera i dettagli completi di un singolo utente.

    Args:
        params: user_key = email o ID utente

    Returns:
        str: Dettagli formattati dell'utente.
    """
    try:
        service = get_directory_service()
        user = service.users().get(userKey=params.user_key).execute()
        return format_user(user)
    except Exception as e:
        return handle_google_error(e)


# =============================================
# TOOL: Crea utente
# =============================================

class CreateUserInput(BaseModel):
    """Input per creazione utente."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    primary_email: str = Field(
        ...,
        description="Email primaria del nuovo utente (es. 'mario.rossi@dominio.it')",
        pattern=r'^[\w\.\-\+]+@[\w\.\-]+\.\w+$',
    )
    first_name: str = Field(..., description="Nome", min_length=1, max_length=60)
    last_name: str = Field(..., description="Cognome", min_length=1, max_length=60)
    password: Optional[str] = Field(
        default=None,
        description="Password iniziale. Se omessa, viene generata automaticamente.",
    )
    org_unit_path: Optional[str] = Field(
        default="/",
        description="Percorso unità organizzativa (es. '/Vendite', '/IT'). Default: root",
    )
    change_password_at_next_login: Optional[bool] = Field(
        default=True,
        description="Forza cambio password al primo accesso",
    )
    recovery_email: Optional[str] = Field(
        default=None,
        description="Email di recupero (opzionale)",
    )
    recovery_phone: Optional[str] = Field(
        default=None,
        description="Telefono di recupero (opzionale, formato: +39...)",
    )


@mcp.tool(
    name="gw_create_user",
    annotations={
        "title": "Crea utente Google Workspace",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def gw_create_user(params: CreateUserInput) -> str:
    """Crea un nuovo utente nel dominio Google Workspace.

    Genera automaticamente una password temporanea se non specificata.
    Di default forza il cambio password al primo login.

    ⚠️ ATTENZIONE: Questa operazione crea un account con licenza.

    Returns:
        str: Conferma creazione con dettagli utente e password temporanea.
    """
    try:
        service = get_directory_service()
        password = params.password or generate_temp_password()

        user_body = {
            "primaryEmail": params.primary_email,
            "name": {
                "givenName": params.first_name,
                "familyName": params.last_name,
            },
            "password": password,
            "changePasswordAtNextLogin": params.change_password_at_next_login,
            "orgUnitPath": params.org_unit_path,
        }

        if params.recovery_email:
            user_body["recoveryEmail"] = params.recovery_email
        if params.recovery_phone:
            user_body["recoveryPhone"] = params.recovery_phone

        created = service.users().insert(body=user_body).execute()

        return (
            f"✅ Utente creato con successo!\n\n"
            f"{format_user(created)}\n\n"
            f"🔑 **Password temporanea**: `{password}`\n"
            f"{'⚠️ L\'utente dovrà cambiarla al primo accesso.' if params.change_password_at_next_login else ''}\n\n"
            f"Comunica le credenziali al cliente in modo sicuro."
        )
    except Exception as e:
        return handle_google_error(e)


# =============================================
# TOOL: Elimina utente
# =============================================

class DeleteUserInput(BaseModel):
    """Input per eliminazione utente."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_key: str = Field(
        ...,
        description="Email o ID dell'utente da eliminare",
        min_length=1,
    )
    confirm: bool = Field(
        ...,
        description="Conferma eliminazione. DEVE essere True per procedere.",
    )


@mcp.tool(
    name="gw_delete_user",
    annotations={
        "title": "Elimina utente Google Workspace",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def gw_delete_user(params: DeleteUserInput) -> str:
    """Elimina permanentemente un utente dal dominio Google Workspace.

    ⚠️ ATTENZIONE: L'utente verrà spostato nel cestino per 20 giorni,
    dopo i quali sarà eliminato definitivamente con tutti i suoi dati.

    Richiede conferma esplicita (confirm=True).

    Returns:
        str: Conferma eliminazione o errore.
    """
    if not params.confirm:
        return (
            "⛔ Eliminazione annullata. Per procedere, imposta confirm=True.\n"
            "Ricorda: l'utente sarà nel cestino per 20 giorni prima dell'eliminazione definitiva."
        )
    try:
        service = get_directory_service()
        user = service.users().get(userKey=params.user_key).execute()
        user_email = user.get("primaryEmail", params.user_key)
        user_name = user.get("name", {}).get("fullName", "N/A")

        service.users().delete(userKey=params.user_key).execute()

        return (
            f"🗑️ Utente eliminato: **{user_name}** ({user_email})\n\n"
            f"L'utente resterà nel cestino per 20 giorni e potrà essere ripristinato.\n"
            f"Dopo 20 giorni l'eliminazione sarà definitiva."
        )
    except Exception as e:
        return handle_google_error(e)


# =============================================
# TOOL: Sospendi / Riattiva utente
# =============================================

class SuspendUserInput(BaseModel):
    """Input per sospensione/riattivazione utente."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_key: str = Field(..., description="Email o ID dell'utente", min_length=1)
    suspend: bool = Field(
        ..., description="True per sospendere, False per riattivare"
    )


@mcp.tool(
    name="gw_suspend_user",
    annotations={
        "title": "Sospendi/Riattiva utente Google Workspace",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def gw_suspend_user(params: SuspendUserInput) -> str:
    """Sospende o riattiva un utente. L'utente sospeso non può accedere ai servizi
    Google ma i suoi dati vengono preservati.

    Returns:
        str: Conferma operazione con stato aggiornato.
    """
    try:
        service = get_directory_service()
        updated = service.users().update(
            userKey=params.user_key,
            body={"suspended": params.suspend}
        ).execute()

        action = "sospeso 🔴" if params.suspend else "riattivato 🟢"
        return (
            f"✅ Utente {action}: **{updated.get('primaryEmail')}**\n\n"
            f"{format_user(updated)}"
        )
    except Exception as e:
        return handle_google_error(e)


# =============================================
# TOOL: Reset password
# =============================================

class ResetPasswordInput(BaseModel):
    """Input per reset password."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_key: str = Field(..., description="Email o ID dell'utente", min_length=1)
    new_password: Optional[str] = Field(
        default=None,
        description="Nuova password. Se omessa, viene generata automaticamente.",
    )
    force_change: Optional[bool] = Field(
        default=True,
        description="Forza cambio password al prossimo login",
    )


@mcp.tool(
    name="gw_reset_password",
    annotations={
        "title": "Reset password utente",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def gw_reset_password(params: ResetPasswordInput) -> str:
    """Resetta la password di un utente. Se non specificata, ne genera una temporanea sicura.

    Returns:
        str: Conferma con nuova password temporanea.
    """
    try:
        service = get_directory_service()
        password = params.new_password or generate_temp_password()

        updated = service.users().update(
            userKey=params.user_key,
            body={
                "password": password,
                "changePasswordAtNextLogin": params.force_change,
            }
        ).execute()

        return (
            f"🔑 Password resettata per: **{updated.get('primaryEmail')}**\n\n"
            f"Nuova password: `{password}`\n"
            f"{'⚠️ L\'utente dovrà cambiarla al prossimo accesso.' if params.force_change else ''}\n\n"
            f"Comunica la nuova password in modo sicuro."
        )
    except Exception as e:
        return handle_google_error(e)


# =============================================
# TOOL: Gestione alias email
# =============================================

class AliasAction(str, Enum):
    ADD = "add"
    REMOVE = "remove"
    LIST = "list"

class ManageAliasInput(BaseModel):
    """Input per gestione alias."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_key: str = Field(..., description="Email o ID dell'utente", min_length=1)
    action: AliasAction = Field(..., description="Azione: 'add', 'remove', o 'list'")
    alias_email: Optional[str] = Field(
        default=None,
        description="Email alias da aggiungere/rimuovere (obbligatorio per add/remove)",
        pattern=r'^[\w\.\-\+]+@[\w\.\-]+\.\w+$',
    )


@mcp.tool(
    name="gw_manage_alias",
    annotations={
        "title": "Gestisci alias email",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def gw_manage_alias(params: ManageAliasInput) -> str:
    """Aggiunge, rimuove o elenca gli alias email di un utente.

    Gli alias permettono di ricevere email su indirizzi alternativi
    senza creare un account separato.

    Returns:
        str: Risultato dell'operazione sugli alias.
    """
    try:
        service = get_directory_service()

        if params.action == AliasAction.LIST:
            result = service.users().aliases().list(userKey=params.user_key).execute()
            aliases = result.get("aliases", [])
            if not aliases:
                return f"Nessun alias configurato per {params.user_key}."
            lines = [f"## Alias per {params.user_key}\n"]
            for a in aliases:
                lines.append(f"- {a.get('alias', 'N/A')}")
            return "\n".join(lines)

        if not params.alias_email:
            return "⚠️ Specifica alias_email per aggiungere o rimuovere un alias."

        if params.action == AliasAction.ADD:
            service.users().aliases().insert(
                userKey=params.user_key,
                body={"alias": params.alias_email}
            ).execute()
            return f"✅ Alias **{params.alias_email}** aggiunto a {params.user_key}"

        elif params.action == AliasAction.REMOVE:
            service.users().aliases().delete(
                userKey=params.user_key,
                alias=params.alias_email,
            ).execute()
            return f"🗑️ Alias **{params.alias_email}** rimosso da {params.user_key}"

    except Exception as e:
        return handle_google_error(e)


# =============================================
# TOOL: Gestione gruppi
# =============================================

class ListGroupsInput(BaseModel):
    """Input per lista gruppi."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_key: Optional[str] = Field(
        default=None,
        description="Se specificato, mostra solo i gruppi di questo utente"
    )
    max_results: Optional[int] = Field(default=100, ge=1, le=500)


@mcp.tool(
    name="gw_list_groups",
    annotations={
        "title": "Lista gruppi Google Workspace",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def gw_list_groups(params: ListGroupsInput) -> str:
    """Elenca i gruppi del dominio o di uno specifico utente.

    Returns:
        str: Lista formattata dei gruppi.
    """
    try:
        service = get_directory_service()
        kwargs = {"customer": CUSTOMER_ID, "maxResults": params.max_results}
        if params.user_key:
            kwargs["userKey"] = params.user_key
            del kwargs["customer"]

        result = service.groups().list(**kwargs).execute()
        groups = result.get("groups", [])

        if not groups:
            return "Nessun gruppo trovato."

        lines = [f"## Gruppi trovati: {len(groups)}\n"]
        for g in groups:
            members_count = g.get("directMembersCount", "?")
            lines.append(
                f"- 👥 **{g.get('email')}** — {g.get('name', 'N/A')} "
                f"({members_count} membri)"
            )
        return "\n".join(lines)

    except Exception as e:
        return handle_google_error(e)


class GroupMemberAction(str, Enum):
    ADD = "add"
    REMOVE = "remove"
    LIST = "list"

class GroupMemberRole(str, Enum):
    MEMBER = "MEMBER"
    MANAGER = "MANAGER"
    OWNER = "OWNER"

class ManageGroupMemberInput(BaseModel):
    """Input per gestione membri gruppo."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    group_key: str = Field(
        ..., description="Email del gruppo", min_length=1
    )
    action: GroupMemberAction = Field(
        ..., description="Azione: 'add', 'remove', o 'list'"
    )
    member_email: Optional[str] = Field(
        default=None,
        description="Email del membro da aggiungere/rimuovere",
    )
    role: Optional[GroupMemberRole] = Field(
        default=GroupMemberRole.MEMBER,
        description="Ruolo nel gruppo: MEMBER, MANAGER, OWNER",
    )


@mcp.tool(
    name="gw_manage_group_member",
    annotations={
        "title": "Gestisci membri gruppo",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def gw_manage_group_member(params: ManageGroupMemberInput) -> str:
    """Aggiunge, rimuove o elenca i membri di un gruppo Google Workspace.

    Returns:
        str: Risultato dell'operazione sui membri del gruppo.
    """
    try:
        service = get_directory_service()

        if params.action == GroupMemberAction.LIST:
            result = service.members().list(groupKey=params.group_key).execute()
            members = result.get("members", [])
            if not members:
                return f"Il gruppo {params.group_key} non ha membri."
            lines = [f"## Membri di {params.group_key}\n"]
            for m in members:
                role = m.get("role", "MEMBER")
                status = m.get("status", "")
                lines.append(f"- {m.get('email', 'N/A')} ({role}) {status}")
            return "\n".join(lines)

        if not params.member_email:
            return "⚠️ Specifica member_email per aggiungere o rimuovere un membro."

        if params.action == GroupMemberAction.ADD:
            service.members().insert(
                groupKey=params.group_key,
                body={
                    "email": params.member_email,
                    "role": params.role.value,
                }
            ).execute()
            return (
                f"✅ **{params.member_email}** aggiunto al gruppo "
                f"**{params.group_key}** come {params.role.value}"
            )

        elif params.action == GroupMemberAction.REMOVE:
            service.members().delete(
                groupKey=params.group_key,
                memberKey=params.member_email,
            ).execute()
            return f"🗑️ **{params.member_email}** rimosso dal gruppo **{params.group_key}**"

    except Exception as e:
        return handle_google_error(e)


# =============================================
# TOOL: Lista unità organizzative
# =============================================

@mcp.tool(
    name="gw_list_org_units",
    annotations={
        "title": "Lista unità organizzative",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def gw_list_org_units() -> str:
    """Elenca tutte le unità organizzative del dominio.

    Le unità organizzative servono per applicare policy diverse
    a diversi gruppi di utenti.

    Returns:
        str: Struttura ad albero delle unità organizzative.
    """
    try:
        service = get_directory_service()
        result = service.orgunits().list(
            customerId=CUSTOMER_ID, type="all"
        ).execute()
        units = result.get("organizationUnits", [])

        if not units:
            return "Nessuna unità organizzativa personalizzata (solo root /)."

        lines = ["## Unità Organizzative\n"]
        for u in sorted(units, key=lambda x: x.get("orgUnitPath", "")):
            lines.append(
                f"- 📁 **{u.get('orgUnitPath')}** — {u.get('name', 'N/A')} "
                f"(ID: {u.get('orgUnitId', 'N/A')})"
            )
        return "\n".join(lines)

    except Exception as e:
        return handle_google_error(e)


# =============================================
# TOOL: Sposta utente in unità organizzativa
# =============================================

class MoveUserOrgInput(BaseModel):
    """Input per spostamento utente tra OU."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_key: str = Field(..., description="Email o ID dell'utente", min_length=1)
    org_unit_path: str = Field(
        ...,
        description="Percorso destinazione (es. '/Vendite', '/IT/Sviluppo')",
        min_length=1,
    )


@mcp.tool(
    name="gw_move_user_org",
    annotations={
        "title": "Sposta utente in unità organizzativa",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def gw_move_user_org(params: MoveUserOrgInput) -> str:
    """Sposta un utente in una diversa unità organizzativa.

    Utile per applicare policy diverse (es. restrizioni app, impostazioni dispositivo).

    Returns:
        str: Conferma spostamento con nuovo percorso OU.
    """
    try:
        service = get_directory_service()
        updated = service.users().update(
            userKey=params.user_key,
            body={"orgUnitPath": params.org_unit_path}
        ).execute()
        return (
            f"✅ **{updated.get('primaryEmail')}** spostato in "
            f"**{params.org_unit_path}**"
        )
    except Exception as e:
        return handle_google_error(e)


# ─────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
