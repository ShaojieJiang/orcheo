# Product Requirements Document

- **Product**: **Orcheo – Visual Workflow Automation Platform**
- **Version**: 1.0
- **Author**: Shaojie Jiang & Claude
- **Date**: 6 September 2025
- **Reviewers**: Shaojie Jiang, Claude

| Rev | Date         | Author(s)           | Notes                           |
| --- | ------------ | ------------------- | ------------------------------- |
| 0.1 | 1 May 2025   | Shaojie Jiang                | Initial skeleton                |
| 0.2 | 21 Jul 2025  | Shaojie Jiang, ChatGPT, Kiro| Backend-first approach pivot    |
| 1.0 | 6 Sep 2025   | Shaojie Jiang, Claude | Comprehensive workflow automation platform |

---

## 1 · Overview

### 1.1 Problem Statement

The workflow automation market includes established players like Zapier and Microsoft Power Automate (SaaS platforms), enterprise solutions, and open-source tools like Apache Airflow and n8n. However, current solutions often force users to choose between simplicity and power, or between visual interfaces and programmatic control. There's an opportunity to build a platform that bridges these gaps with modern AI capabilities, serving both low-code users through visual design and code-first developers through programmatic APIs.

### 1.2 Goal

Build Orcheo as a comprehensive workflow automation platform that uniquely bridges the gap between low-code visual tools and code-first programmatic approaches, differentiating from existing market solutions through modern AI-first design and robust LangGraph infrastructure.

**Core Value Proposition:**
- **Dual Development Experience**: Low-code visual designer for business users + Python SDK for developers
- **AI-first architecture** with native LangGraph integration for intelligent workflows
- **Flexible deployment** - Use as Python library or standalone server
- **Extensible node ecosystem** with growing library of pre-built integrations
- **Integration-ready** with secure credential management for 3rd party APIs, execution persistence, and monitoring
- **Multiple trigger methods** supporting webhooks, cron schedules, and manual execution

### 1.3 Scope (v1.0)

**Frontend (React Flow Canvas)**
- Visual workflow designer with drag-and-drop interface
- Node library with 20+ essential integrations
- Workflow validation with real-time error checking
- Execution monitoring with live status updates
- Credential management UI
- Workflow versioning and templates

**Backend (Dual-Mode Architecture)**
- **Python Library Mode**: Node library for LangGraph integration, letting code-first developers focus on node definitions while LangGraph handles graph and state management
- **Standalone Server Mode**: FastAPI-based REST API for low-code applications
- Workflow execution engine powered by LangGraph
- Secure credential vault for API keys, OAuth tokens, and 3rd party service authentication
- Multiple trigger systems (webhooks, cron, manual)
- Execution persistence and history
- Real-time WebSocket updates

**Core Node Types (v1.0)**
- **Triggers**: Webhook, Cron, Manual, HTTP Polling
- **AI/LLM**: OpenAI, Anthropic, Custom AI Agent, Text Processing
- **Data**: HTTP Request, JSON Processing, Data Transform
- **Logic**: If/Else, Switch, Merge, Set Variable
- **Database**: MongoDB, PostgreSQL, SQLite
- **Communication**: Email, Slack, Telegram, Discord
- **Utilities**: Code (Python/JavaScript), Delay, Debug

**Advanced Workflow Features (v1.0)**
- Loops and iterative processing
- Sub-workflows and workflow composition
- Parallel branches and concurrent execution

### 1.4 Out-of-Scope (v1.0)

- Enterprise SSO and advanced RBAC
- Multi-tenancy and team workspaces
- Advanced monitoring and alerting
- Marketplace for community nodes
- Mobile applications
- On-premises deployment options
- Advanced debugging tools (breakpoints, step-through)

---

## 2 · Architecture Overview

### 2.1 System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │  Backend Server │    │   Execution     │
│   (React +      │◄──►│   (FastAPI +    │◄──►│   (LangGraph    │
│   React Flow)   │    │    SQLite)      │    │   + Celery)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │
         │               ┌─────────────────┐
         └──────────────►│ Python Library  │
                         │   (LangGraph    │
                         │    Direct)      │
                         └─────────────────┘
```

**Frontend Stack:**
- React 18+ with TypeScript
- React Flow for canvas interactions
- Zustand for state management
- TanStack Query for server state
- Tailwind CSS + shadcn/ui components

**Backend Stack:**
- **Server Mode**: FastAPI with asyncio for low-code users
- **Library Mode**: Node library for LangGraph integration, with developers handling graph and state management directly
- LangGraph for workflow execution engine
- SQLite for development, PostgreSQL for production
- Redis for caching and job queues (server mode)
- Celery for background task processing (server mode)

### 2.2 Data Flow

**Low-Code Path (Visual Designer):**
1. **Design Phase**: User creates workflows in React Flow canvas
2. **Translation**: Frontend converts React Flow graph to LangGraph-compatible format
3. **Storage**: Backend validates and stores workflow definitions
4. **Execution**: Triggers invoke LangGraph execution engine via server
5. **Monitoring**: Real-time updates via WebSocket connections

**Code-First Path (Python Library):**
1. **Definition**: Developers define custom nodes using Orcheo's node library and use LangGraph directly for graph and state management
2. **Direct Execution**: LangGraph workflows run directly in developer's environment
3. **Integration**: Optional server integration for persistence and monitoring
4. **Deployment**: Workflows can run standalone or integrate with server infrastructure

---

## 3 · User Stories

| User                        | User Story                                             |
| --------------------------- | ------------------------------------------------------ |
| **Maya** – Business Analyst | As a business analyst, I want to create data processing workflows using a visual canvas so that I can build complex data pipelines without writing code |
| **Sam** – Marketing Manager | As a marketing manager, I want to build automation workflows through a low-code interface so that I can streamline marketing processes without technical dependencies |
| **Tom** – SaaS Founder      | As a SaaS founder, I want a hybrid approach combining visual design with custom Python components so that I can rapidly prototype while maintaining technical flexibility |
| **Dev** – Full-Stack Developer | As a full-stack developer, I want to use a Python SDK for complex integrations and custom nodes so that I can extend workflows with programmatic control |
| **Jake** – Backend Developer | As a backend developer, I want to orchestrate API calls and internal services with secure credential management so that I can build reliable system integrations without exposing sensitive data |
| **Chris** – Integration Specialist | As an integration specialist, I want to configure webhook endpoints and cron schedules with monitoring and error handling so that I can ensure reliable automated workflows between systems |
| **Lisa** – Data Scientist   | As a data scientist, I want a code-first approach for AI model chaining and analysis so that I can build sophisticated ML workflows with full control |
| **Amy** – ML/AI Engineer    | As an ML/AI engineer, I want to build and trace multi-step AI agent workflows with detailed execution logs so that I can debug model performance and optimize AI-powered data pipelines |

---

## 4 · Functional Requirements

### 4.1 Frontend - Visual Workflow Designer

**Canvas Interface**
- Drag-and-drop nodes from sidebar to canvas
- Visual connections between node inputs/outputs
- Pan, zoom, and minimap navigation
- Grid snapping and alignment helpers
- Undo/redo functionality with keyboard shortcuts

**Node Management**
- Node search and categorization
- Real-time input validation and error display
- Collapsible node configuration panels
- Node duplication and deletion
- Custom node styling and labeling

**Workflow Operations**
- Save, load, and duplicate workflows
- Import/export workflow definitions (JSON)
- Workflow templates and examples library
- Version history with diff visualization
- Workflow sharing via exported files

### 4.2 Backend - Dual-Mode Architecture

**Server Mode (FastAPI) - For Low-Code Users**

*Workflow Management API*
- `POST /workflows` - Create new workflow
- `GET /workflows/{id}` - Retrieve workflow definition
- `PUT /workflows/{id}` - Update workflow
- `DELETE /workflows/{id}` - Delete workflow
- `GET /workflows` - List workflows with pagination

*Execution Management*
- `POST /workflows/{id}/execute` - Manual execution
- `GET /executions/{id}` - Get execution status
- `GET /executions` - List execution history
- `DELETE /executions/{id}` - Cancel running execution
- WebSocket `/ws/executions/{id}` - Real-time updates

**Library Mode (Python SDK) - For Code-First Developers**

*Node Definition Focus*
```python
from orcheo import AINode, HTTPNode
from langgraph import StateGraph

# Define custom nodes using Orcheo's node library
fetch_node = HTTPNode("fetch-data", url="api.example.com")
analyze_node = AINode("analyze", model="gpt-4")

# Graph and state management handled by LangGraph
graph = StateGraph(state_schema)
graph.add_node("fetch", fetch_node)
graph.add_node("analyze", analyze_node)
graph.add_edge("fetch", "analyze")

# Execute using LangGraph
result = await graph.invoke(initial_state)
```

*Optional Server Integration*
- Register workflows with server for persistence
- Stream execution logs to server for monitoring
- Leverage server credential management
- Access shared workflow templates and nodes

**3rd Party Integration Credentials**
- Encrypted storage of API keys, OAuth tokens, and service credentials (AES-256)
- Pre-built credential templates for popular services (Slack, Google, AWS, etc.)
- Credential testing and validation before workflow execution
- Scoped credential access per workflow to prevent unauthorized usage
- Automatic OAuth token refresh and credential rotation

### 4.3 Trigger Systems

**Webhook Triggers**
- Dynamic webhook URL generation
- Request validation and filtering
- Support for GET, POST, PUT, DELETE methods
- Custom response configuration
- Rate limiting and security headers

**Cron Triggers**
- Standard cron expression syntax
- Timezone-aware scheduling
- Execution history and failure handling
- Overlap prevention options
- Pause/resume functionality

**Manual Triggers**
- One-click execution from UI
- Batch execution with different inputs
- Execution with custom variables
- Debug mode with step-by-step execution

### 4.4 Node Library

**AI/LLM Nodes**
- OpenAI integration (GPT-4, embeddings, DALL-E)
- Anthropic Claude integration
- Custom AI agent with tool calling
- Text summarization and analysis
- Sentiment analysis and classification

**Integration Nodes**
- HTTP Request with authentication
- Database connectors (SQL, NoSQL)
- File operations (read, write, transform)
- Email sending (SMTP, services)
- Slack, Discord, Telegram messaging

**Logic Nodes**
- Conditional branching (If/Else)
- Switch node for multi-path routing
- Data merging and aggregation
- Variable setting and manipulation
- Error handling and retry logic

---

## 5 · Technical Specifications

### 5.1 Frontend Requirements

**Performance**
- Canvas renders 500+ nodes smoothly (60fps)
- Node search results in <100ms
- Workflow save/load in <2 seconds
- Real-time execution updates with <200ms latency

**Browser Compatibility**
- Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- Progressive Web App (PWA) capabilities
- Offline workflow editing (with sync on reconnect)

**Accessibility**
- WCAG 2.1 AA compliance
- Keyboard navigation for all canvas operations
- Screen reader support for workflow structure
- High contrast mode support

### 5.2 Backend Requirements

**Performance**
- API response time <200ms (95th percentile)
- Support 1000+ concurrent workflow executions
- Handle 10K+ workflows per instance
- Execution logs queryable within 5 seconds

**Security**
- JWT-based authentication
- Rate limiting (100 req/min per user)
- Input sanitization and validation
- Secure credential encryption at rest
- HTTPS-only communication

**Scalability**
- Horizontal scaling via load balancer
- Database connection pooling
- Background job processing with Celery
- Redis caching for frequently accessed data

---

## 6 · Success Metrics

### 6.1 Development Metrics (6 months post-development)

| Metric | Target |
|--------|--------|
| Personal workflows | 20+ |
| Monthly executions | 1,000+ |
| Node library size | 20+ nodes |
| Integration coverage | 10+ services |
| Automation success rate | >90% |

### 6.2 Technical Metrics

| Metric | Target |
|--------|--------|
| Local development stability | >95% uptime |
| Average execution time | <5 seconds |
| Frontend responsiveness | <2 seconds |
| Workflow success rate | >90% |
| Test coverage | >80% |

### 6.3 Development Experience Metrics

| Metric | Target |
|--------|--------|
| Time to first workflow | <5 minutes |
| Workflow iteration speed | <2 minutes |
| Development productivity | 3x manual processes |
| Error debugging efficiency | <10 minutes average |
| Feature completeness | Core use cases covered |

---

## 7 · Development Timeline

### Phase 1: Foundation (Months 1-3)
- **Python SDK**: Node library for LangGraph integration with 3rd party service nodes
- **Open-Source Dev Server**: Local development server as free LangGraph Studio alternative
- **Visual Canvas**: Basic React Flow implementation with essential nodes
- **Server API**: Backend for persistence and low-code workflow management
- Essential integration nodes (Slack, HTTP, OpenAI, PostgreSQL, etc.)
- 3rd party service credential management

### Phase 2: Integration (Months 4-5)
- **Server Features**: Webhook and cron trigger systems, credential vault for integrations
- **SDK Enhancement**: Advanced 3rd party integrations (Google Workspace, AWS, MongoDB, etc.)
- **Dev Server Features**: Execution tracing, performance metrics, debugging tools
- Advanced node library (20+ integrations) across both platforms
- Real-time execution monitoring and WebSocket streaming

### Phase 3: Polish (Months 6-7)
- Advanced canvas features (templates, versioning)
- Comprehensive error handling and debugging
- Security hardening and compliance
- Documentation and tutorial creation
- Beta testing and feedback incorporation

### Phase 4: Launch (Month 8)
- Production deployment and monitoring
- Performance testing and optimization
- Community engagement and support setup
- Marketing and user acquisition
- Post-launch iteration planning

---

## 8 · Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|---------|------------|
| React Flow performance issues | Medium | High | Early prototyping and performance testing |
| LangGraph integration complexity | High | Medium | Proof of concept and iterative development |
| Node development bottleneck | Medium | Medium | Community contribution framework |
| Security vulnerabilities | Low | High | Security audit and pen testing |
| User adoption challenges | Medium | High | User research and iterative UX improvements |

---

## 9 · Technical Dependencies

### 9.1 Frontend Dependencies
- `react-flow` - Canvas and node management
- `@tanstack/react-query` - Server state management
- `zustand` - Client state management
- `tailwindcss` - Styling framework
- `shadcn/ui` - Component library

### 9.2 Backend Dependencies
- `fastapi` - Web framework
- `langgraph` - Workflow execution engine
- `langchain` - AI integration framework
- `sqlalchemy` - Database ORM
- `celery` - Background task processing
- `redis` - Caching and message broker

---

## 10 · Future Roadmap (Post v1.0)

### v1.1 - Advanced Features
- Advanced debugging tools
- Team workspaces and collaboration
- Workflow marketplace

### v1.2 - Enterprise
- SSO and advanced authentication
- Audit logging and compliance
- Advanced monitoring and alerting
- On-premises deployment options

### v2.0 - AI-Enhanced
- AI-assisted workflow creation
- Smart node recommendations
- Automatic error resolution
- Natural language workflow queries

---

*This PRD serves as the foundational document for building Orcheo as a comprehensive workflow automation platform that bridges low-code visual design with code-first programmatic development.*
