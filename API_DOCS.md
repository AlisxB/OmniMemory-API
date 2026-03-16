# Documentação Técnica: OmniMemory API v1

A OmniMemory é uma API especializada em fornecer um "cérebro persistente" para agentes de inteligência artificial conversacional. Ela gerencia contexto, memória de longo prazo, transcrição de áudio e buffering de mensagens de forma segura e escalável.

---

## 📑 Sumário

1. [Conceitos Fundamentais](#conceitos-fundamentais)
2. [Autenticação](#autenticação)
3. [Endpoints de Contexto (v1)](#contexto)
4. [Endpoints de Memória (v1)](#memória)
5. [Endpoints de Áudio (v1)](#áudio)
6. [Webhooks e Eventos](#webhooks)
7. [Guia de Integração n8n](#guia-n8n)

---

## 🧠 Conceitos Fundamentais

Para utilizar a API corretamente, é importante entender os seguintes termos:

*   **Tenant:** Representa uma conta ou cliente (ex: "michel_vereador"). Cada tenant possui suas próprias chaves e isolamento de dados.
*   **External User ID:** O identificador único do usuário no seu canal (ex: número do WhatsApp ou e-mail).
*   **Sessão (Session):** Um agrupamento temporal de mensagens. Uma sessão expira após um período de inatividade (configurável).
*   **Buffer Window:** Uma janela de tempo (segundos) onde a API aguarda mensagens "picotadas" antes de disparar um gatilho de resposta final.
*   **Memória (Memory):** Fatos extraídos da conversa que são armazenados permanentemente e recuperados via busca semântica (vectores).

---

## 🔐 Autenticação

Todas as requisições devem incluir o header de autenticação:

*   **Header:** `X-API-Key`
*   **Formato:** `tenant_id:omni__secret_key`

> [!IMPORTANT]
> Nunca compartilhe sua API Key no front-end. Utilize-a apenas em ambientes de back-end ou orquestradores como n8n.

---

## 💬 Contexto

Endpoints usados para gerenciar o fluxo de mensagens e o contexto histórico.

### `POST /v1/context/resolve`
**Quando usar:** No início de qualquer interação para identificar o usuário e carregar o contexto.

*   **Body (JSON):**
    ```json
    {
      "tenant_id": "string",
      "external_user_id": "string",
      "channel": "whatsapp | telegram | web",
      "metadata": {}
    }
    ```
*   **O que retorna:** Detalhes da sessão ativa, o histórico recente de mensagens e as **memórias** relevantes (busca semântica).

### `POST /v1/context/message`
**Quando usar:** Para salvar cada mensagem (do usuário ou do assistente) no histórico.

*   **Body (JSON):**
    ```json
    {
      "tenant_id": "string",
      "session_id": "uuid",
      "role": "user | assistant",
      "content": "Conteúdo da mensagem"
    }
    ```

---

## 💾 Memória

Gerenciamento de fatos persistentes sobre o usuário.

### `POST /v1/memory`
**Quando usar:** Para salvar uma informação que o bot deve "aprender" sobre o usuário.

*   **Body (JSON):**
    ```json
    {
      "tenant_id": "string",
      "external_user_id": "string",
      "key": "identificador_unico",
      "value": "Descrição do fato",
      "scope": "user"
    }
    ```
*   **Nota:** Se a `key` já existir para esse usuário, o valor será atualizado.

---

## 🔊 Áudio

### `POST /v1/audio/process`
**Quando usar:** Para converter áudios do WhatsApp/Telegram em texto.

*   **Input:** `file` (Upload) ou `url` (Link público do áudio).
*   **Tecnologia:** Groq Whisper v3 (Ultra rápido).

---

## 🪝 Webhooks

A API dispara notificações para o seu servidor/n8n nos seguintes eventos:

1.  **`message.created`:** Imediato. Disparado quando uma mensagem é salva.
2.  **`session.ready`:** Disparado após o fechamento da janela de **Buffer**, contendo todas as mensagens agrupadas.
3.  **`memory.updated`:** Quando uma nova memória é criada ou editada.

---

## � Estrutura de Resposta Padrão

Todas as respostas (sucesso ou erro) seguem este formato para facilitar o rastreamento:

```json
{
  "status": "success | error",
  "data": { ... },
  "request_id": "uuid-do-request",
  "timestamp": "2024-03-12T..."
}
```

---

## ⚠️ Códigos de Erro Comuns

| Código | Descrição | Motivo Comum |
| :--- | :--- | :--- |
| **401** | Unauthorized | API Key ausente ou inválida. |
| **403** | Forbidden | A chave não pertence ao `tenant_id` informado. |
| **404** | Not Found | Endpoint ou recurso (usuário/webhook) inexistente. |
| **422** | Unprocessable Entity | Erro de validação no JSON enviado. |
| **429** | Too Many Requests | Você atingiu seu limite de mensagens por minuto. |

---

## 🪝 Detalhamento de Webhooks

Abaixo, os campos enviados no body do seu Webhook (n8n):

### Evento: `session.ready`
Este é o evento mais importante para o seu bot responder ao usuário.

*   **Payload Exemplo:**
    ```json
    {
      "event": "session.ready",
      "tenant_id": "michel_vereador",
      "sessionid": "a3eab0ca...",
      "external_user_id": "558592499236",
      "content": "Olá! Gostaria de saber mais sobre o projeto.",
      "full_content": "Olá! Gostaria de saber mais sobre o projeto.",
      "data": { ... }
    }
    ```

---

## 🛠 Guia de Integração n8n

### Passo 1: Receber a Mensagem
No n8n, use um nó de **Webhook** configurado para o método `POST`. Copie a URL gerada e cadastre-a na API OmniMemory via Dashboard ou Endpoint de Webhooks.

### Passo 2: Evitar o Loop Infinito (CRÍTICO)
Ao chamar o nó de **HTTP Request** para salvar a resposta do Assistente:
1.  URL: `https://api.desenrolaai.tech/v1/context/message`
2.  Method: `POST`
3.  JSON:
    ```json
    {
      "tenant_id": "seu_tenant",
      "session_id": "{{ $json.sessionid }}",
      "role": "assistant",
      "content": "{{ $json.output_da_ia }}"
    }
    ```
> [!TIP]
> Por que o `role: assistant`? A OmniMemory API nunca dispara webhooks para mensagens criadas pelo assistente, garantindo que o bot não responda a si mesmo.

---

## 🔍 Busca Semântica Manual

Se precisar buscar algo na memória sem ser durante o `resolve`:
`GET /v1/context/search?tenant_id=michel&external_user_id=5585...&query=Onde ele mora?&limit=3`
