# 🤖 Ferramenta de Verificação de Estudante Google One (Gemini) - Web e CLI

Ferramenta de verificação de estudante para o Google One AI Premium (Gemini Advanced 2TB + Veo + NotebookLM Pro) pelo portal SheerID.

Oferece uma **interface Web visual**. Pode ser implantada no **Railway** ou executada localmente (CLI / Web).

---

## 🌟 Principais recursos

- 🌐 **Console Web moderno**:
  - Interface em modo escuro, otimizada para computador e celular.
  - Acompanhe o progresso da verificação e veja o **log ao vivo no terminal** em tempo real (Server-Sent Events).
  - Gera e exibe automaticamente prévias de: **Carteirinha de estudante (ID Card)**, **Grade de horários (Class Schedule)** e **Recibo de mensalidade (Tuition Receipt)**.
  - Permite baixar as imagens dos documentos para enviá-los manualmente, se preferir.
- 🚀 **Automação completa (Full Automation)**:
  - Gera automaticamente identidades de estudantes americanos (nome completo, data de nascimento, e-mail EDU, NetID, número de matrícula).
  - Resolve o CAPTCHA Cloudflare Turnstile pela API do 2Captcha.
  - Passa automaticamente pela etapa de SSO da universidade.
  - Envia os documentos direto para o S3 do SheerID e dispara o processo de análise.
  - **Auto Polling**: acompanha continuamente o resultado em tempo real.
- 🛡️ **Anti-detecção e gerenciamento de IP residencial**:
  - Aloca e atribui automaticamente um **IP de proxy residencial fixo (sticky)** (Proxy-Cheap, EUA).
  - Verifica e monitora o IP durante toda a sessão de verificação, evitando troca de IP no meio do processo.
  - Simula a impressão digital do navegador (User-Agent, headers NewRelic, hash de fingerprint).
- 🏫 **Separação por perfil de universidade (Ivy vs State)**:
  - UC Berkeley (State)
  - MIT - Massachusetts Institute of Technology (Ivy)
  - Harvard University (Ivy)
  - UIUC - University of Illinois (State)
  - UPenn - University of Pennsylvania (Ivy)
  - University of Florida (State)

---

## 🚀 Guia de implantação no Railway (Deploy to Railway)

### Opção 1: Implantação via GitHub (Recomendada)

1. Envie o código-fonte para o seu GitHub:
   ```bash
   cd D:\gem-doc\one-verify-tool
   git init
   git add .
   git commit -m "feat: initial commit for Railway deployment"
   git branch -M main
   git remote add origin https://github.com/<username>/one-verify-tool.git
   git push -u origin main
   ```
2. Faça login no [Railway.app](https://railway.app/).
3. Clique em **New Project** ➔ escolha **Deploy from GitHub repo** ➔ selecione o repositório `one-verify-tool`.
4. O Railway detectará o `Dockerfile` automaticamente e construirá a aplicação com Chromium headless e Python.
5. Configure as variáveis de ambiente (Variables) no Railway:
   - `PORT`: fornecida pelo Railway (padrão 8080).
   - `CAPTCHA_API_KEY`: sua chave do 2Captcha para resolver CAPTCHAs.
   - `HCTI_USER_ID`: (Opcional) User ID da API HCTI.
   - `HCTI_API_KEY`: (Opcional) API Key da API HCTI.
   - `PROXY_USER`: (Opcional) Usuário do proxy residencial Proxy-Cheap.
   - `PROXY_PASS_BASE`: (Opcional) Senha base do proxy residencial.
   - `PROXY_HOST`: `thehub.proxy-cheap.com`
   - `PROXY_PORT`: `8080`
6. Vá na aba **Settings** ➔ na seção **Networking**, clique em **Generate Domain** para obter o link de acesso à web (por exemplo: `https://one-verify-production.up.railway.app`).

---

## 💻 Guia de execução local (Local)

### 1. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 2. Iniciar a interface Web

```bash
python app.py
```
Ou:
```bash
python main.py --web
```
Acesse no navegador: **http://localhost:8080**

### 3. Iniciar a interface de linha de comando (CLI)

```bash
# Informar o link de forma interativa pelo terminal:
python main.py

# Ou passar o link diretamente:
python main.py "https://services.sheerid.com/verify/67c8c14f5f17a83b745e3f82/?verificationId=..."

# Apenas gerar os documentos, sem enviar:
python main.py "URL" --docs-only
```

---

## 📡 Endpoints da API (para bots / automação)

A ferramenta oferece uma API REST com Swagger UI em `/docs`:

- `GET /health`: Verifica o estado do servidor (healthcheck).
- `GET /api/stats`: Retorna estatísticas da taxa de sucesso.
- `GET /api/universities`: Lista as universidades suportadas.
- `POST /api/verify`: Inicia o processo de verificação.
- `GET /api/verify/{task_id}/events`: Transmite o log em tempo real via Server-Sent Events (SSE).
- `GET /api/verify/{task_id}/status`: Consulta o estado do processo em JSON.
- `GET /api/docs/{dir_name}/{filename}`: Baixa um documento gerado.
