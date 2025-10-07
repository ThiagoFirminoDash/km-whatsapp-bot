# KM WhatsApp Bot (Flask + SQLite + Twilio)

Registre **KM inicial/final**, **corridas (R$)** e **abastecimentos** (tipo, valor e litros) **pelo WhatsApp** e receba um **resumo diário automaticamente** no próprio WhatsApp.

## ✅ O que este bot faz
- Recebe mensagens via WhatsApp (Twilio Sandbox/Produção)
- Comandos:
  - `km inicio 32000`
  - `km final 32210`
  - `corrida 25` **ou** `corrida 12, 18, 34`
  - `abasteci etanol 120 28` *(tipo, valor R$, litros)*
  - `resumo` *(de hoje)* ou `resumo AAAA-MM-DD`
- Calcula e retorna:
  - KM rodado (final – inicial)
  - Ganhos totais
  - Gasto com combustível (e **preço médio por litro**)
  - **Lucro do dia**
  - **Custo por KM**
- Envia **resumo automático** no fim do dia (via `/cron/send_daily`).

---

## 1) Requisitos
- Python 3.10+
- Conta **Twilio** com **WhatsApp Sandbox** ativado (trial serve)
- Internet pública para receber webhooks (Ngrok para teste, VPS/render/railway para produção)

### Variáveis de ambiente
```bash
# obrigatório para enviar mensagens (resumo diário) e responder no WhatsApp
export TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxx"
export TWILIO_AUTH_TOKEN="xxxxxxxxxxxxxxxxxxxxxxx"
export TWILIO_WHATSAPP_FROM="whatsapp:+14155238886"   # número do sandbox

# opcional: caminho do banco (SQLite)
export DB_PATH="km_driver.db"
```

> No Windows PowerShell, use `setx` (persistente) ou `set` (sessão atual):
> ```powershell
> setx TWILIO_ACCOUNT_SID "ACxxxxxxxx..."
> setx TWILIO_AUTH_TOKEN  "xxxxxxxx..."
> setx TWILIO_WHATSAPP_FROM "whatsapp:+14155238886"
> ```

---

## 2) Instalação rápida
```bash
python -m venv .venv
# Linux/Mac
source .venv/bin/activate
# Windows PowerShell
# .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

---

## 3) Rodando local + expondo com Ngrok
Em um terminal:
```bash
python app.py
# Running on http://127.0.0.1:5000
```

Em outro terminal:
```bash
ngrok http 5000
```
Copie a URL HTTPS do ngrok (ex.: `https://a1b2c3d4.ngrok.io`).

No **Twilio Console → Messaging → WhatsApp Sandbox → Sandbox configuration**:
- Em **WHEN A MESSAGE COMES IN** cole:  
  `https://a1b2c3d4.ngrok.io/whatsapp`  → **Save**.

### Conectar seu WhatsApp ao Sandbox
Na mesma página do Sandbox, envie do seu WhatsApp a mensagem de **join** indicada (ex.: `join sunny-river`) para o número apresentado (ex.: `+1 415 523 8886`).

---

## 4) Teste pelo WhatsApp
No chat do número do Twilio (sandbox), envie:
```
ajuda

km inicio 12000
corrida 25
abasteci etanol 120 28
km final 12180
resumo
```

Você deve receber o resumo do dia. A timezone é **America/Sao_Paulo**.

---

## 5) Resumo automático (23:59) – CRON
Para receber **no WhatsApp**:

```bash
# exemplo de CRON diário às 23:59 (Ubuntu/Debian)
crontab -e
# adicione a linha abaixo (troque o domínio e o seu número):
59 23 * * * /usr/bin/curl -s "https://SEU_DOMINIO/cron/send_daily?user=whatsapp:+55SEUNUMERO" >> /var/log/km-bot-cron.log 2>&1
```

> Em ambiente free (Render/Railway), use o **scheduler** para chamar a URL diariamente.

---

## 6) Produção (opcional)
- Suba em uma VPS (Hostinger, DO, Contabo) ou PaaS (Render/Railway).
- Use **Gunicorn + Nginx** em VPS:
  - `gunicorn -w 2 -b 127.0.0.1:5000 app:app`
  - Proxy Nginx em `seu.dominio.com` → `127.0.0.1:5000`

---

## 7) Estrutura
```
km-whatsapp-bot/
├── app.py
├── requirements.txt
└── README.md
```

O banco SQLite (`km_driver.db`) é criado automaticamente no primeiro uso.

---

## 8) Comandos disponíveis (no WhatsApp)
- `km inicio 32000`
- `km final 32210`
- `corrida 25`  |  `corrida 12, 18, 34`
- `abasteci etanol 120 28`  |  `abasteci gasolina 200 33.5`
- `resumo`  |  `resumo 2025-10-07`
- `ajuda`

---

## 9) Observações
- No **Sandbox**, apenas números que enviaram o comando **join** conseguem falar com o bot.
- Para usar **em número próprio (produção)**, é preciso validar o número no WhatsApp Business (Meta) e ativar no Twilio.
- Mensagens **outbound** (o bot te enviar sem você falar antes) no sandbox funcionam para números que já estão “joined”.

Bom proveito! 🚀
