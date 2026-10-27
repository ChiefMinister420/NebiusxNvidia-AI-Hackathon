# RelayDesk

**A grounded support copilot for teams that want to answer faster without making things up.** RelayDesk searches a small help-center knowledge base, prepares a customer-ready draft, and highlights next steps and human-review risk. It is designed for the **Best Apps and Agents** track of the Nebius × NVIDIA Global AI Hackathon.

The live generation path uses **NVIDIA Nemotron-3.5-Lightning** served by **Nebius Token Factory** through its OpenAI-compatible API. Each triage request also calls the **Tavily Search API** at runtime when `TAVILY_API_KEY` is configured. Tavily searches a topic derived from the matched help article (never the raw customer message), and its web results are shown separately from company guidance. The app also runs in a clearly labeled offline demo mode, so the interface can be explored without credentials.

## What it does

1. Paste a customer message or load one of the example tickets.
2. RelayDesk retrieves relevant passages from its help-center articles using local keyword matching.
3. When configured, RelayDesk makes a runtime `POST https://api.tavily.com/search` call for public context. The query uses the top matched article title, or a generic support query if no article matches; customer message text is not sent to Tavily.
4. In live mode, Nemotron uses company excerpts for company-specific claims and treats Tavily results as untrusted public context, then drafts a reply with next steps and escalation guidance.
5. Review the matched articles and separately labeled Tavily results, assess the risk cue, and copy the draft into your support system.

RelayDesk does not send replies or connect to customer accounts. The included articles are fictional example content. Replace them with your approved support guidance before use.

## Project structure

```text
.
├── app.py              # Small Python HTTP server, retrieval, Tavily and Nebius API clients
├── knowledge.json      # Editable example help-center articles
├── web/index.html      # Responsive single-page interface
├── Dockerfile          # Container for local or Nebius AI Cloud deployment
├── .env.example        # Runtime configuration template
└── README.md
```

No Python packages are required. The server uses Python's standard library.

## Run locally

Requirements: Python 3.10 or newer.

```bash
git clone <your-repository-url>
cd <your-repository-directory>
cp .env.example .env
```

For the offline preview, leave both API keys unset. Start the app:

```bash
set -a
source .env
set +a
python app.py
```

Open [http://localhost:8000](http://localhost:8000). Use the sample tickets and leave **Demo mode** on to see local retrieval and illustrative draft behavior. Demo drafts are templates, not model output.

## Connect Nebius Token Factory, Nemotron, and Tavily

1. Create or sign in to a Nebius Token Factory account and create an API key in the Token Factory console.
2. Put the key in `.env` as `NEBIUS_API_KEY`. Do not commit `.env` or expose the key in browser code.
3. Keep `NEBIUS_MODEL=nvidia/Nemotron-3_5-Lightning` for the default efficient agent model. If a model ID or endpoint has changed in your Token Factory catalog, use the ID shown there.
4. Restart `python app.py`. The header should show **Nemotron ready**. Turn **Demo mode** off and draft a sample ticket; the result banner displays the selected model.

To enable runtime Tavily search, create a Tavily API key and set `TAVILY_API_KEY` in `.env` or `tavily.env` in the project folder. RelayDesk reads either file at startup. After restarting, the header shows Tavily search readiness; each **Draft a reply** action makes a Tavily search request, even with Demo mode selected. Results appear in their own **Tavily Web Search** section. If Tavily is not configured, only local help-center retrieval runs. These key files are ignored by Git.

The default endpoint is `https://api.tokenfactory.nebius.com/v1`, and RelayDesk calls `/chat/completions`. Override it with `NEBIUS_BASE_URL` if your account or endpoint uses a different base URL. You can select another compatible Nemotron model by changing `NEBIUS_MODEL`.

Example `.env`:

```dotenv
NEBIUS_API_KEY=replace-with-your-token-factory-key
TAVILY_API_KEY=replace-with-your-tavily-key
NEBIUS_MODEL=nvidia/Nemotron-3_5-Lightning
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1
PORT=8000
```

Both API keys stay on the server. The browser sends the ticket to the RelayDesk backend; the backend sends it and retrieved help excerpts to Nebius Token Factory for inference. Only an article-topic query is sent to Tavily; raw ticket text is not sent to Tavily. Avoid entering personal or sensitive customer data unless you have permission and an appropriate data-handling policy.

## Run with Docker

Build and start the container:

```bash
docker build -t relaydesk .
docker run --rm -p 8000:8000 \
  -e NEBIUS_API_KEY="$NEBIUS_API_KEY" \
  -e TAVILY_API_KEY="$TAVILY_API_KEY" \
  -e NEBIUS_MODEL="nvidia/Nemotron-3_5-Lightning" \
  relaydesk
```

Open [http://localhost:8000](http://localhost:8000). For demo mode, omit `NEBIUS_API_KEY`.

## Deploy on Nebius AI Cloud

RelayDesk makes inference calls to Token Factory, so the web app itself does not need a GPU. A small Linux VM with Docker is enough; size it for expected concurrent web requests and your desired availability.

1. Create a Linux VM in Nebius AI Cloud and make sure it can reach the public internet for Token Factory requests.
2. Install Docker using the package instructions for the VM's Linux distribution.
3. Copy or clone this project onto the VM, then build the image with `docker build -t relaydesk .`.
4. Store `NEBIUS_API_KEY` and `TAVILY_API_KEY` in the VM's secret manager or protected service environment. Do not bake them into the image or place them in source control.
5. Run the container, mapping your chosen listening port to container port `8000` and setting `PORT=8000` inside the container. Restrict inbound traffic to your intended users; put a TLS-enabled reverse proxy or load balancer in front of it for an internet-facing deployment.
6. Configure the VM firewall / security group to allow only the required inbound web traffic. The app health endpoint is `GET /api/health`.

Example on the VM after Docker is installed and the key is present in the shell environment:

```bash
docker run -d --name relaydesk --restart unless-stopped \
  -p 8000:8000 \
  -e NEBIUS_API_KEY="$NEBIUS_API_KEY" \
  -e TAVILY_API_KEY="$TAVILY_API_KEY" \
  -e NEBIUS_MODEL="nvidia/Nemotron-3_5-Lightning" \
  relaydesk
```

For a managed or Kubernetes-based deployment, build and push the same Docker image to a registry available to your cluster, then provide the API key through the platform's secret mechanism and expose the service through its ingress/load-balancer path. Keep the key out of container build arguments and manifests committed to Git.

## Configure the knowledge base

Edit `knowledge.json`. Each article has an `id`, a short `title`, and plain-text `content`. IDs are included in model citations and must be unique. Restart the server after edits. Keep articles concise and policy-approved. Retrieval is intentionally simple and lexical; it is a hackathon-sized starter, not a production search or access-control system.

## How it is built

- **Frontend:** single responsive HTML/CSS/JavaScript page; no frontend build step.
- **Backend:** Python standard-library HTTP server with `/api/health` and `/api/triage`.
- **Retrieval:** local token-overlap ranking over `knowledge.json`, returning up to four relevant excerpts.
- **Live web research:** Tavily Search API call on each triage request when `TAVILY_API_KEY` is set; its query is based on a help-topic title, not ticket text.
- **Generation:** Nebius Token Factory OpenAI-compatible chat completions with `nvidia/Nemotron-3_5-Lightning` by default.
- **Safety cues:** the prompt asks the model not to invent policy, requires source IDs, and requests a risk label and human-review guidance. The interface always treats output as an unsent draft.

## Known limitations and next steps

- The bundled demo articles and example tickets are fictional; replace them before evaluating with real workflows.
- Keyword retrieval can miss paraphrases and does not understand article freshness, permissions, or conflicting policies. A next version could use embeddings and a properly permissioned source connector.
- Model output is not guaranteed to be correct. Review every draft; escalate security, legal, payment, and account-recovery cases through your established process.
- The included server is suitable for a hackathon prototype. For production, add authentication, rate limiting, structured logs with sensitive data redacted, durable monitoring, and a hardened production web server.
- Tavily results are public web content and may be inaccurate or irrelevant. They are shown separately and must not be treated as company policy. Always verify citations and statements against displayed sources.

## Credits and useful links

- [Nebius Token Factory](https://tokenfactory.nebius.com/)
- [Nebius Token Factory inference documentation](https://docs.tokenfactory.nebius.com/)
- [Nebius page: NVIDIA Nemotron inference](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference)
- [Nebius Token Factory Nemotron cookbook](https://github.com/nebius/token-factory-cookbook/tree/main/models/nemotron)
- [Tavily Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search)

Built for the Nebius × NVIDIA Global AI Hackathon — **Best Apps and Agents**.
