# 🎬 GraphCorp: 3-Minute Demo Video Recording Script

**Project:** GraphCorp — The Autonomous AI Software Enterprise Powered by FalkorDB  
**Event:** WeMakeDevs Graph Hacks (Track 01: Agents That Act on Connected Data)  
**Target Time:** Exactly 3 Minutes (0:00 – 3:00)

---

## ⏱️ Video Timeline Overview

| Timestamp | Phase | Visual Target | Key Narration Focus |
| :--- | :--- | :--- | :--- |
| **0:00 - 0:35** | **The Hook** | Camera / Title Slide & Vector Failure Graphic | Why chat logs and vector stores fail; introducing FalkorDB as the company OS. |
| **0:35 - 1:45** | **The Live Run** | Split Screen: Web Dashboard & CLI Terminal | Real-time Cytoscape graph nodes lighting up; CEO → CTO → PM → Dev → QA → DevOps; real git commits. |
| **1:45 - 2:30** | **FalkorDB Deep Dive** | Dashboard Inspector Pane & Cypher Queries | Sub-millisecond Topological Task Dispatch and AST blast-radius calculations. |
| **2:30 - 3:00** | **The Real Result** | Terminal Fullscreen | Authentic `git log --graph`, 100% passing pytests, live execution of `dev-vault` CLI. |

---

## 📜 Scene-by-Scene Script & Production Guide

### [0:00 – 0:35] Scene 1: The Hook & The Problem
**Visual:**  
- **0:00 - 0:15:** Speaker on webcam with title card: *"GraphCorp: The Autonomous AI Software Enterprise Powered by FalkorDB"*.
- **0:15 - 0:35:** Cut to split graphic comparing *Flat Vector Search / LLM Chat Buffers* vs. *GraphCorp Unified Graph Engine*. Show the "Context Drift & Hallucination" warning sign over vector stores.

**Audio / Voiceover:**  
> *"Every autonomous AI agent framework today is stuck in the same trap: they rely on flat vector databases and endless chat histories.*  
>  
> *In a real software company, this causes immediate failure: context drift, amnesia, topological blindspots, and broken dependencies. You cannot run a company on cosine similarity.*  
>  
> *Meet **GraphCorp**. GraphCorp is an autonomous AI software company where the CEO, CTO, Product Manager, Developers, QA, and DevOps engineers operate on a single, unified operating system: **FalkorDB**.*  
>  
> *FalkorDB stores the organizational hierarchy, the recursive task DAG, the code AST knowledge graph, and the Git provenance in a living, low-latency graph."*

---

### [0:35 – 1:45] Scene 2: The Live Autonomous Run
**Visual:**  
- **0:35 - 0:50:** Split screen. On the right, terminal launches:
  ```bash
  python run_corp.py --prompt "Build dev-vault: an enterprise developer secret store CLI with AES-256 GCM"
  ```
- **0:50 - 1:20:** On the left, browser is open to `http://localhost:8000` (GraphCorp Mission Control).
  - The CEO agent node pulses purple (`#8A2BE2`) and creates a Strategic Decision node.
  - The CTO breaks it down into technical specifications.
  - The PM decomposes it into a 6-node Task DAG with `BLOCKED_BY` edges.
  - Developer agents pick up unblocked tasks, write genuine code, and commit to feature branches.
  - QA agent triggers, calculates blast radius, runs automated pytests, and approves PRs.
  - DevOps agent verifies green checks and performs non-fast-forward merge commits to `main`.
- **1:20 - 1:45:** Watch the Cytoscape graph dynamically expand from 6 nodes to 33 nodes and 76 relationships as tasks transition from Orange (Blocked) to Purple (Active) to Emerald Green (Done).

**Audio / Voiceover:**  
> *"Let’s watch GraphCorp work live. We give the prompt: 'Build dev-vault, an enterprise secret store CLI with AES-256-GCM authenticated encryption and Argon2id.'*  
>  
> *Instantly, our Executive Tier activates. The CEO formulates strategy, the CTO defines architecture, and the Product Manager builds a dependency DAG in FalkorDB.*  
>  
> *Notice our developers aren't polling or guessing. Through FalkorDB, they query the graph for unblocked tasks whose prerequisites are 100% satisfied.*  
>  
> *Here, the Developer agent writes the cryptography module and opens PR-TASK-02. Before QA approves it, they query FalkorDB to calculate the blast radius across the AST, execute a real pytest run via MCP, and sign off. DevOps immediately executes a clean merge commit to main, unblocking downstream tasks in under a tenth of a millisecond."*

---

### [1:45 – 2:30] Scene 3: FalkorDB Deep Dive & Multi-Hop Cypher
**Visual:**  
- **1:45 - 2:05:** Zoom in on Pane 2 (Multi-Hop Reasoning Inspector) on the Mission Control dashboard. Click on `TASK-04` (`feat/cli-interface`) and `crypto.py`.
- **2:05 - 2:30:** Cut to code overlay showing the live Cypher queries:
  1. *Topological Task Dispatch:*
     ```cypher
     MATCH (t:Task) WHERE t.status = 'TODO'
       AND NOT (t)-[:BLOCKED_BY]->(:Task {status: 'TODO'})
     RETURN t.id, t.title ORDER BY t.priority LIMIT 1
     ```
  2. *Multi-Hop AST Blast Radius:*
     ```cypher
     MATCH (target:Component {name: 'crypto.py'})<-[:CALLS*1..3]-(c:Component)
     RETURN c.name, collect(t.name)
     ```
  Highlight the execution metrics badge: **`Traversed upstream AST in 0.08ms: 8 impacted`**.

**Audio / Voiceover:**  
> *"Why does FalkorDB make this possible?*  
>  
> *First: Recursive DAG resolution. In relational SQL, resolving multi-level dependencies requires expensive recursive CTEs that choke under scale. In FalkorDB, our topological task dispatch query evaluates the graph in **0.02 milliseconds**.*  
>  
> *Second: AST Blast Radius. When a file is modified, a vector store cannot tell you which caller will break. With FalkorDB, our QA agent runs a 3-hop traversal through `:CALLS` relationships to discover every affected component and associated test suite in **0.08 milliseconds**.*  
>  
> *Third: Complete Governance Provenance. Every commit SHA in Git is linked back to the PR, the task, the developer, and the original CEO decision node. There is zero hallucination and total auditability."*

---

### [2:30 – 3:00] Scene 4: The Real Result (Zero Demoware)
**Visual:**  
- **2:30 - 2:42:** Switch to fullscreen terminal in `workspace/dev-vault`:
  ```bash
  git -C workspace/dev-vault log --graph --oneline
  ```
  Highlight the clean branching, commit messages, and merge commits.
- **2:42 - 2:52:** Run pytest:
  ```bash
  pytest workspace/dev-vault/tests/ -v
  ```
  Show **8 passed in 0.32s**.
- **2:52 - 3:00:** Execute the compiled CLI live:
  ```bash
  python workspace/dev-vault/src/cli.py init --passphrase "GraphHacks2026!" --path vault.enc
  python workspace/dev-vault/src/cli.py set AWS_SECRET "AKIAIOSFODNN7EXAMPLE" --passphrase "GraphHacks2026!" --path vault.enc
  python workspace/dev-vault/src/cli.py get AWS_SECRET --passphrase "GraphHacks2026!" --path vault.enc
  ```
  The decrypted secret appears instantly!
- **End:** Cut back to presenter with the GraphCorp banner and FalkorDB badge.

**Audio / Voiceover:**  
> *"Most importantly: GraphCorp does not produce demoware or simulated markdown.*  
>  
> *Look at `workspace/dev-vault`. Here is the genuine Git graph: real feature branches, real commit SHAs, and real non-fast-forward merge commits.*  
>  
> *All 8 automated security and unit tests pass with 100% green coverage.*  
>  
> *And the CLI is fully operational right now—initializing an AES-256-GCM vault, encrypting secrets with Argon2id, and retrieving them with zero data leakage.*  
>  
> *This is the future of autonomous engineering: AI agents that don't just guess, but reason and act on connected data. Powered by FalkorDB. Thank you!"*

---

## 🛠️ Recording Checklist for Presenter

- [ ] Terminal font size set to 16pt+, high-contrast theme (Solarized Dark or One Dark).
- [ ] Browser window sized to 1920x1080 at 100% zoom.
- [ ] Pre-run `pytest tests/ -v` to ensure everything is cached and warmed up.
- [ ] Have a fresh vault path `/tmp/demo_vault.enc` ready for the live CLI demo.
- [ ] Ensure FalkorDB server or embedded engine is active and responding.
