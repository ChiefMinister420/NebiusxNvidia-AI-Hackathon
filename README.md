# NebiusxNvidia-AI-Hackathon
# RelayDesk

**A grounded support copilot for teams that want to answer faster without making things up.** RelayDesk searches a small help-center knowledge base, prepares a customer-ready draft, and highlights next steps and human-review risk. It is designed for the **Best Apps and Agents** track of the Nebius × NVIDIA Global AI Hackathon.

The live generation path uses **NVIDIA Nemotron-3.5-Lightning** served by **Nebius Token Factory** through its OpenAI-compatible API. The app also runs in a clearly labeled offline demo mode, so the interface and retrieval flow can be explored without credentials.

## What it does

1. Paste a customer message or load one of the example tickets.
2. RelayDesk retrieves relevant passages from its help-center articles using local keyword matching.
3. In live mode, Nemotron drafts a reply using only those passages, plus a short action list and escalation guidance.
4. Review the matched articles, assess the risk cue, and copy the draft into your support system.

RelayDesk does not send replies or connect to customer accounts. The included articles are fictional example content. Replace them with your approved support guidance before use.

## Project structure

```text
.
├── app.py              # Small Python HTTP server, retrieval, and Nebius API client
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

For the offline preview, leave the API key unset. Start the app:

```bash
set -a
source .env
set +a
python app.py
```

Open [http://localhost:8000](http://localhost:8000). Use the sample tickets and leave **Demo mode** on to see local retrieval and illustrative draft behavior. Demo drafts are templates, not model output.

## Connect Nebius Token Factory and Nemotron

1. Create or sign in to a Nebius Token Factory account and create an API key in the Token Factory console.
2. Put the key in `.env` as `NEBIUS_API_KEY`. Do not commit `.env` or expose the key in browser code.
3. Keep `NEBIUS_MODEL=nvidia/Nemotron-3_5-Lightning` for the default efficient agent model. If a model ID or endpoint has changed in your Token Factory catalog, use the ID shown there.
4. Restart `python app.py`. The header should show **Nemotron ready**. Turn **Demo mode** off and draft a sample ticket; the result banner displays the selected model.

The default endpoint is `https://api.tokenfactory.nebius.com/v1`, and RelayDesk calls `/chat/completions`. Override it with `NEBIUS_BASE_URL` if your account or endpoint uses a different base URL. You can select another compatible Nemotron model by changing `NEBIUS_MODEL`.

Example `.env`:

```dotenv
NEBIUS_API_KEY=replace-with-your-token-factory-key
NEBIUS_MODEL=nvidia/Nemotron-3_5-Lightning
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1
PORT=8000
```

The API key stays on the server. The browser sends the ticket to the RelayDesk backend; the backend sends the ticket and retrieved help excerpts to Nebius Token Factory for inference. Avoid entering personal or sensitive customer data unless you have permission and an appropriate data-handling policy.

## Run with Docker

Build and start the container:

```bash
docker build -t relaydesk .
docker run --rm -p 8000:8000 \
  -e NEBIUS_API_KEY="$NEBIUS_API_KEY" \
  -e NEBIUS_MODEL="nvidia/Nemotron-3_5-Lightning" \
  relaydesk
```

Open [http://localhost:8000](http://localhost:8000). For demo mode, omit `NEBIUS_API_KEY`.

## Deploy on Nebius AI Cloud

RelayDesk makes inference calls to Token Factory, so the web app itself does not need a GPU. A small Linux VM with Docker is enough; size it for expected concurrent web requests and your desired availability.

1. Create a Linux VM in Nebius AI Cloud and make sure it can reach the public internet for Token Factory requests.
2. Install Docker using the package instructions for the VM's Linux distribution.
3. Copy or clone this project onto the VM, then build the image with `docker build -t relaydesk .`.
4. Store `NEBIUS_API_KEY` in the VM's secret manager or protected service environment. Do not bake it into the image or place it in source control.
5. Run the container, mapping your chosen listening port to container port `8000` and setting `PORT=8000` inside the container. Restrict inbound traffic to your intended users; put a TLS-enabled reverse proxy or load balancer in front of it for an internet-facing deployment.
6. Configure the VM firewall / security group to allow only the required inbound web traffic. The app health endpoint is `GET /api/health`.

Example on the VM after Docker is installed and the key is present in the shell environment:

```bash
docker run -d --name relaydesk --restart unless-stopped \
  -p 8000:8000 \
  -e NEBIUS_API_KEY="$NEBIUS_API_KEY" \
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
- **Generation:** Nebius Token Factory OpenAI-compatible chat completions with `nvidia/Nemotron-3_5-Lightning` by default.
- **Safety cues:** the prompt asks the model not to invent policy, requires source IDs, and requests a risk label and human-review guidance. The interface always treats output as an unsent draft.

## Known limitations and next steps

- The bundled demo articles and example tickets are fictional; replace them before evaluating with real workflows.
- Keyword retrieval can miss paraphrases and does not understand article freshness, permissions, or conflicting policies. A next version could use embeddings and a properly permissioned source connector.
- Model output is not guaranteed to be correct. Review every draft; escalate security, legal, payment, and account-recovery cases through your established process.
- The included server is suitable for a hackathon prototype. For production, add authentication, rate limiting, structured logs with sensitive data redacted, durable monitoring, and a hardened production web server.
- Local keyword retrieval shows the matching articles, but the current model prompt asks for citations in text and only accepts source IDs that match retrieved articles. Always verify citations and statements against the displayed excerpts.

## Credits and useful links

- [Nebius Token Factory](https://tokenfactory.nebius.com/)
- [Nebius Token Factory inference documentation](https://docs.tokenfactory.nebius.com/)
- [Nebius page: NVIDIA Nemotron inference](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference)
- [Nebius Token Factory Nemotron cookbook](https://github.com/nebius/token-factory-cookbook/tree/main/models/nemotron)

Built for the Nebius × NVIDIA Global AI Hackathon — **Best Apps and Agents**.
