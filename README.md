# 🔧 Google Workspace MCP Server

<!-- mcp-name: io.github.aringad/google-workspace-mcp -->

🇮🇹 Italiano | [🇬🇧 English](#english)

---

## Italiano

Server MCP (Model Context Protocol) per gestire **Google Workspace** tramite Claude AI e altri assistenti compatibili. Permette di amministrare utenti, gruppi, alias e unità organizzative tramite conversazione naturale.

### ✨ Funzionalità

| Tool | Descrizione |
|------|-------------|
| `gw_list_users` | Lista utenti con ricerca e filtri |
| `gw_get_user` | Dettaglio completo di un utente |
| `gw_create_user` | Crea nuovo utente con password auto-generata |
| `gw_delete_user` | Elimina utente (con conferma obbligatoria) |
| `gw_suspend_user` | Sospendi o riattiva un utente |
| `gw_reset_password` | Reset password con generazione automatica |
| `gw_manage_alias` | Aggiungi, rimuovi, elenca alias email |
| `gw_list_groups` | Lista gruppi del dominio o di un utente |
| `gw_manage_group_member` | Aggiungi/rimuovi membri dai gruppi |
| `gw_list_org_units` | Lista unità organizzative |
| `gw_move_user_org` | Sposta utente tra unità organizzative |

### 📋 Prerequisiti

- Python 3.10+
- Account Google Workspace con accesso admin
- Progetto Google Cloud con Admin SDK API abilitata
- Claude Desktop o altro client MCP

### 🚀 Installazione

```bash
pip install google-workspace-mcp
```

Oppure da sorgente:

```bash
git clone https://github.com/aringad/google-workspace-mcp.git
cd google-workspace-mcp
pip install -r requirements.txt
```

### 🔑 Configurazione Google Cloud

#### 1. Crea progetto e abilita API

1. Vai su [console.cloud.google.com](https://console.cloud.google.com)
2. Crea un nuovo progetto (o usa quello esistente)
3. Vai su **API e servizi → Libreria**
4. Cerca e abilita: **Admin SDK API**

#### 2. Crea Service Account

1. Vai su **API e servizi → Credenziali**
2. **Crea credenziali → Account di servizio**
3. Dai un nome (es. `mcp-workspace-admin`)
4. Vai nel Service Account → **Chiavi → Aggiungi chiave → JSON**
5. Scarica il file JSON (queste sono le tue credenziali)
6. **Annota il Client ID** (numero lungo nei dettagli del Service Account)

> ⚠️ Non serve assegnare ruoli IAM al Service Account. I permessi vengono dalla delega domain-wide.

#### 3. Delega Domain-Wide

1. Vai su [admin.google.com](https://admin.google.com)
2. **Sicurezza → Accesso e controllo dati → Controlli API → Gestisci delega a livello di dominio**
3. Clicca **Aggiungi nuovo**
4. Inserisci il **Client ID** del Service Account
5. Come ambiti OAuth, inserisci:

```
https://www.googleapis.com/auth/admin.directory.user,https://www.googleapis.com/auth/admin.directory.group,https://www.googleapis.com/auth/admin.directory.orgunit,https://www.googleapis.com/auth/admin.directory.user.alias
```

6. **Autorizza**

### ⚙️ Variabili d'ambiente

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path al file JSON delle credenziali | `./credentials.json` |
| `GOOGLE_ADMIN_EMAIL` | Email del super admin con delega | *(obbligatorio)* |
| `GOOGLE_CUSTOMER_ID` | Customer ID del dominio | `my_customer` |

### 🔌 Configurazione Claude Desktop

Aggiungi al file di configurazione:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "google_workspace": {
      "command": "/percorso/completo/google-workspace-mcp/venv/bin/python",
      "args": ["/percorso/completo/google-workspace-mcp/server.py"],
      "env": {
        "GOOGLE_SERVICE_ACCOUNT_FILE": "/percorso/completo/credentials.json",
        "GOOGLE_ADMIN_EMAIL": "admin@tuodominio.it"
      }
    }
  }
}
```

Chiudi completamente Claude Desktop (Cmd+Q su Mac) e riaprilo.

#### 🏢 Configurazione multi-cliente

Puoi gestire più domini aggiungendo istanze separate:

```json
{
  "mcpServers": {
    "gw_cliente_alfa": {
      "command": "/percorso/venv/bin/python",
      "args": ["server.py"],
      "env": {
        "GOOGLE_SERVICE_ACCOUNT_FILE": "/percorso/credentials-alfa.json",
        "GOOGLE_ADMIN_EMAIL": "admin@alfa.it"
      }
    },
    "gw_cliente_beta": {
      "command": "/percorso/venv/bin/python",
      "args": ["server.py"],
      "env": {
        "GOOGLE_SERVICE_ACCOUNT_FILE": "/percorso/credentials-beta.json",
        "GOOGLE_ADMIN_EMAIL": "admin@beta.it"
      }
    }
  }
}
```

### 💬 Esempi d'uso

Una volta configurato, puoi dire a Claude:

- *"Mostrami tutti gli utenti del dominio"*
- *"Crea un nuovo utente mario.rossi@dominio.it, nome Mario Rossi"*
- *"Sospendi l'utente luigi@dominio.it"*
- *"Resetta la password di marco@dominio.it"*
- *"Aggiungi l'alias info@dominio.it all'utente segreteria@dominio.it"*
- *"Aggiungi mario@dominio.it al gruppo vendite@dominio.it"*
- *"In che unità organizzative è diviso il dominio?"*

Puoi anche copiare direttamente l'email del cliente con la richiesta e Claude interpreterà automaticamente le operazioni da eseguire.

### 🔒 Sicurezza

- Le credenziali del Service Account **non vanno mai committate** nel repository
- Le password temporanee generate sono di 16 caratteri con lettere, numeri e simboli
- Le operazioni distruttive (eliminazione) richiedono conferma esplicita
- Il Service Account opera con i soli permessi strettamente necessari
- Nessun dato viene memorizzato dal server MCP

### 🧪 Test

```bash
# Verifica che il server parta
python server.py --help

# Test con MCP Inspector
npx @modelcontextprotocol/inspector python server.py
```

---

## English

<a name="english"></a>

MCP (Model Context Protocol) Server to integrate **Google Workspace Admin** with Claude AI and other compatible assistants. Manage users, groups, aliases and organizational units through natural conversation.

### ✨ Features

| Tool | Description |
|------|-------------|
| `gw_list_users` | List users with search and filters |
| `gw_get_user` | Full user details |
| `gw_create_user` | Create new user with auto-generated password |
| `gw_delete_user` | Delete user (requires explicit confirmation) |
| `gw_suspend_user` | Suspend or reactivate a user |
| `gw_reset_password` | Reset password with automatic generation |
| `gw_manage_alias` | Add, remove, list email aliases |
| `gw_list_groups` | List domain or user groups |
| `gw_manage_group_member` | Add/remove group members |
| `gw_list_org_units` | List organizational units |
| `gw_move_user_org` | Move user between organizational units |

### 📋 Prerequisites

- Python 3.10+
- Google Workspace account with admin access
- Google Cloud project with Admin SDK API enabled
- Claude Desktop or another MCP client

### 🚀 Installation

```bash
pip install google-workspace-mcp
```

Or from source:

```bash
git clone https://github.com/aringad/google-workspace-mcp.git
cd google-workspace-mcp
pip install -r requirements.txt
```

### 🔑 Google Cloud Setup

#### 1. Create project and enable API

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use existing one)
3. Go to **APIs & Services → Library**
4. Search and enable: **Admin SDK API**

#### 2. Create Service Account

1. Go to **APIs & Services → Credentials**
2. **Create Credentials → Service Account**
3. Name it (e.g., `mcp-workspace-admin`)
4. Go to the Service Account → **Keys → Add Key → JSON**
5. Download the JSON file (these are your credentials)
6. **Note the Client ID** (long number in Service Account details)

> ⚠️ No IAM roles needed on the Service Account. Permissions come from domain-wide delegation.

#### 3. Domain-Wide Delegation

1. Go to [admin.google.com](https://admin.google.com)
2. **Security → Access and data control → API controls → Manage Domain Wide Delegation**
3. Click **Add new**
4. Enter the Service Account **Client ID**
5. For OAuth scopes, enter:

```
https://www.googleapis.com/auth/admin.directory.user,https://www.googleapis.com/auth/admin.directory.group,https://www.googleapis.com/auth/admin.directory.orgunit,https://www.googleapis.com/auth/admin.directory.user.alias
```

6. **Authorize**

### ⚙️ Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to credentials JSON file | `./credentials.json` |
| `GOOGLE_ADMIN_EMAIL` | Super admin email with delegation | *(required)* |
| `GOOGLE_CUSTOMER_ID` | Domain customer ID | `my_customer` |

### 🔌 Claude Desktop Configuration

Add to config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "google_workspace": {
      "command": "/full/path/to/google-workspace-mcp/venv/bin/python",
      "args": ["/full/path/to/google-workspace-mcp/server.py"],
      "env": {
        "GOOGLE_SERVICE_ACCOUNT_FILE": "/full/path/to/credentials.json",
        "GOOGLE_ADMIN_EMAIL": "admin@yourdomain.com"
      }
    }
  }
}
```

Fully quit Claude Desktop (Cmd+Q on Mac) and reopen it.

### 💬 Usage Examples

Once configured, you can tell Claude:

- *"Show me all domain users"*
- *"Create a new user john.doe@domain.com, name John Doe"*
- *"Suspend user jane@domain.com"*
- *"Reset the password for mark@domain.com"*
- *"Add the alias info@domain.com to user secretary@domain.com"*
- *"Add john@domain.com to the sales@domain.com group"*
- *"What organizational units does the domain have?"*

You can also paste client emails with requests directly — Claude will automatically interpret the operations to perform.

### 🔒 Security

- Service Account credentials must **never be committed** to the repository
- Temporary passwords are 16 characters with letters, numbers, and symbols
- Destructive operations (deletion) require explicit confirmation
- The Service Account operates with minimum necessary permissions
- No data is stored by the MCP server

### 🧪 Testing

```bash
# Verify server starts
python server.py --help

# Test with MCP Inspector
npx @modelcontextprotocol/inspector python server.py
```

---

## 📄 License

MIT License — See [LICENSE](LICENSE) for details.

## 👨‍💻 Author

Developed by **[Mediaform s.c.r.l.](https://www.media-form.it)** — Genova, Italy

---

*Built with [MCP](https://modelcontextprotocol.io) and [Google Admin SDK](https://developers.google.com/admin-sdk)*
