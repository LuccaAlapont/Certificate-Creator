# Briefing — Certificate Creator (deploy em VPS)

## O que é o projeto
Aplicação web para geração em lote de certificados personalizados (nome impresso sobre uma imagem de template). Feita para uso interno de uma instituição de saúde. Deve ser acessível apenas por usuários autorizados pois tem o Google Drive do usuário conectado.

**Repositório GitHub (privado):** `https://github.com/LuccaAlapont/Certificate-Creator`

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.10+, FastAPI, Uvicorn |
| Frontend | HTML/CSS/JS puro (sem framework) |
| Banco de dados | SQLite (`templates.db`) — armazena metadados dos templates |
| Geração de imagem | Pillow (PIL) |
| Planilhas | openpyxl |
| Google Drive | google-api-python-client, google-auth-oauthlib |
| Auth | Sessão via cookie HttpOnly (`cc_session`) — sem biblioteca extra |

---

## Estrutura de pastas

```
certificate-creator/
├── backend/
│   ├── main.py              # FastAPI app + middleware de sessão
│   ├── database.py          # SQLite helpers
│   └── routes/
│       ├── auth.py          # login / logout / check
│       ├── templates.py     # CRUD de templates
│       ├── generate.py      # geração em lote (thread worker)
│       ├── convert.py       # conversor imagem → PDF
│       └── drive.py         # integração Google Drive
│   └── services/
│       ├── gdrive.py        # lógica OAuth2 + upload
│       ├── image_gen.py     # renderização do certificado com Pillow
│       ├── name_parser.py   # parse de texto e planilhas
│       └── cleanup.py       # limpeza periódica de outputs
├── frontend/
│   ├── index.html           # app principal
│   ├── login.html           # tela de login
│   ├── css/style.css
│   └── js/
│       ├── api.js / app.js / auth.js / convert.js / drive.js
├── templates/               # PNGs dos modelos (NÃO está no git — sobe manualmente)
├── fonts/                   # fontes TTF (NÃO está no git — sobe manualmente)
├── uploads/                 # onde os templates ficam após upload pela UI
├── outputs/                 # ZIPs/PDFs gerados (limpos automaticamente após 7 dias)
├── templates.db             # SQLite (NÃO está no git — criado automaticamente)
├── gdrive-credentials.json  # credencial OAuth2 do Google (NÃO está no git — sensível)
├── gdrive-token.json        # token OAuth2 salvo (NÃO está no git — sensível)
├── gdrive-config.json       # ID da pasta do Drive + ano (NÃO está no git)
├── requirements.txt
└── run.py                   # entrypoint: uvicorn na porta 8001
```

---

## Variáveis de ambiente obrigatórias no servidor

```bash
APP_USER=admin           # usuário da tela de login
APP_PASSWORD=suasenha    # senha da tela de login (sem isso, o app abre sem login)
OUTPUT_MAX_DAYS=7        # opcional — dias para manter arquivos gerados (padrão 7)
```

---

## Como fazer deploy no VPS (Linux)

```bash
# 1. Clonar o repositório
git clone https://github.com/LuccaAlapont/Certificate-Creator.git
cd Certificate-Creator

# 2. Criar ambiente virtual e instalar dependências
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Criar as pastas que não estão no git
mkdir -p templates fonts uploads outputs

# 4. Definir variáveis de ambiente
export APP_USER=admin
export APP_PASSWORD=suasenhasegura

# 5. Rodar
uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

---

## Autenticação (como funciona)

- Ao acessar qualquer rota sem sessão válida → redireciona para `/login`
- Login via `POST /api/auth/login` com `{username, password}` → cria cookie `cc_session` (HttpOnly, SameSite=Lax, 7 dias)
- Logout via `POST /api/auth/logout` → destroi sessão no servidor e limpa cookie
- Sessões ficam **em memória** — reiniciar o servidor desloga todos (aceitável para uso interno)
- Credenciais configuradas pelas variáveis `APP_USER` e `APP_PASSWORD`

---

## Google Drive (ponto de atenção)

- A integração usa **OAuth2 do próprio usuário** (não service account)
- O arquivo `gdrive-credentials.json` (credencial do Google Cloud Console) e `gdrive-token.json` (token salvo) precisam existir no servidor mas **não estão no git**
- O redirect URI do OAuth está hardcoded como `http://localhost:8001/api/drive/oauth-callback` — **no VPS precisa ser atualizado** para o domínio/IP real no arquivo `backend/services/gdrive.py` linha 15 e no Google Cloud Console

---

## Recomendações para produção

- Colocar **Nginx na frente** como proxy reverso com HTTPS (Let's Encrypt)
- Rodar o app como **systemd service** para restart automático
- Adicionar `secure=True` no `set_cookie` do `backend/routes/auth.py` linha 50 quando HTTPS estiver ativo
- Atualizar o `REDIRECT_URI` do Drive para o domínio real
