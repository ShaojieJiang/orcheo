# Architecture of this project

The design philosophy of this project can be summarised as follows:
1. Backend-first: The backend is the core of the project, and the frontend is a powerful extension but optional. Developers can also design their own frontend or clients to interact with the backend.
2. Low-code and code-first: Normal users and developers can just specify configuration to use the platform. Advanced developers can use components in the Python SDK in code-first manner.

## Backend

```mermaid
graph TD
    subgraph "Users"
        Developers["Developers (Code-first)"]
        GUIUsers["GUI Users (Low-code)"]
    end

    subgraph "API Gateway & Security"
        Gateway[API Gateway]
        Auth[Auth Service]
        RateLimit[Rate Limiter]
        LB[Load Balancer]
    end

    subgraph "Application Layer"
        APIs["REST API Instances (1, 2, ...)"]
        WS[WebSocket Service]
    end

    subgraph "Workflow Runtime"
        NodeLibrary[Node Library]
        GraphBuilder[Graph Builder]
        GraphRuntimes["Graph Runtime Instances (1, 2, ...)"]
        MessageBroker[Message Broker]
        Celery[Celery Workers]
        CircuitBreaker[Circuit Breaker]
        RetryHandler[Retry Handler]
    end

    subgraph "Data Layer"
        Cache[(Redis Cache)]
        ConfigDB[(Config DB)]
        RuntimeDB[(Runtime DB)]
        UserDB[(User DB)]
        CredentialsDB[(Credentials DB)]
        BackupDB[(Backup Storage)]
    end

    subgraph "Observability & Monitoring"
        Monitoring[Monitoring Service]
        Logging[Logging Service]
        Tracing[Distributed Tracing]
        AlertManager[Alert Manager]
    end

    subgraph "External Services"
        ServiceProviders[Service Providers]
        DeadLetterQueue[Dead Letter Queue]
    end

    subgraph "DevOps & Deployment"
        CICD[CI/CD Pipeline]
        Container[Container Registry]
        Orchestrator[Kubernetes/Docker]
    end

    Developers -.-> Gateway
    GUIUsers -.-> Gateway
    Gateway --> Auth
    Gateway --> RateLimit
    Gateway --> LB
    LB --> APIs
    APIs --> WS
    APIs --> NodeLibrary
    APIs --> GraphBuilder
    APIs --> MessageBroker
    MessageBroker --> Celery
    Celery --> GraphRuntimes
    GraphRuntimes --> Cache
    GraphBuilder --> ConfigDB
    GraphRuntimes --> RuntimeDB
    Auth --> UserDB
    NodeLibrary --> CircuitBreaker
    CircuitBreaker --> ServiceProviders
    RetryHandler --> ServiceProviders
    ServiceProviders --> CredentialsDB
    ServiceProviders --> DeadLetterQueue

    %% Monitoring connections
    APIs --> Monitoring
    GraphRuntimes --> Logging
    GraphRuntimes --> Tracing
    Monitoring --> AlertManager

    %% Backup connections
    ConfigDB --> BackupDB
    RuntimeDB --> BackupDB
    UserDB --> BackupDB
    CredentialsDB --> BackupDB

    %% DevOps connections
    CICD --> Container
    Container --> Orchestrator
    Orchestrator --> APIs

    %% Styling
    classDef userNodes fill:#e1f5fe,stroke:#0277bd,stroke-width:2px,stroke-dasharray: 5 5,opacity:0.7
    classDef securityNodes fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef observabilityNodes fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef dataNodes fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    classDef devopsNodes fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef reliabilityNodes fill:#fff8e1,stroke:#ff8f00,stroke-width:2px

    class Developers,GUIUsers,Users userNodes
    class Gateway,Auth,RateLimit,LB securityNodes
    class Monitoring,Logging,Tracing,AlertManager observabilityNodes
    class Cache,ConfigDB,RuntimeDB,UserDB,BackupDB,CredentialsDB dataNodes
    class CICD,Container,Orchestrator devopsNodes
    class CircuitBreaker,RetryHandler,DeadLetterQueue reliabilityNodes
```

## Frontend

```mermaid
graph TD
    subgraph "User Interface Layer"
        AuthUI[Authentication UI]
        Dashboard[Dashboard]
        CanvasUI[Workflow Canvas UI]
        SettingsUI[Settings UI]
    end

    subgraph "Core Modules"
        AuthModule[Authentication Module]
        CanvasModule[Workflow Canvas]
        NodeLibraryModule[Node Library]
        TracesModule[Traces & Monitoring]
        ConfigModule[Configuration Module]
    end

    subgraph "Node & Graph Management"
        NodeEditor[Node Editor]
        AgenticTools[Agentic Tools Manager]
        SubgraphConfig[Sub-graph Configuration]
        GraphConfig[Graph Configuration]
        NodeRegistry[Node Registry]
    end

    subgraph "API Communication"
        APIClient[API Client]
        WebSocketClient[WebSocket Client]
        AuthService[Auth Service]
        WorkflowService[Workflow Service]
        NodeService[Node Service]
    end

    subgraph "Utilities & Services"
        ValidationService[Validation Service]
        CacheService[Cache Service]
        EventBus[Event Bus]
        NotificationService[Notification Service]
        ThemeService[Theme Service]
    end

    %% UI to Module connections
    AuthUI --> AuthModule
    Dashboard --> TracesModule
    CanvasUI --> CanvasModule
    CanvasUI --> NodeLibraryModule
    SettingsUI --> ConfigModule

    %% Module to Node/Graph Management
    CanvasModule --> NodeEditor
    CanvasModule --> GraphConfig
    NodeLibraryModule --> NodeRegistry
    NodeEditor --> AgenticTools
    NodeEditor --> SubgraphConfig
    ConfigModule --> GraphConfig

    %% API Communication connections
    AuthModule --> AuthService
    CanvasModule --> WorkflowService
    NodeLibraryModule --> NodeService
    TracesModule --> WebSocketClient
    AuthService --> APIClient
    WorkflowService --> APIClient
    NodeService --> APIClient
    NodeService --> WebSocketClient

    %% Utilities connections
    NodeEditor --> ValidationService
    GraphConfig --> ValidationService
    APIClient --> CacheService
    TracesModule --> NotificationService
    CanvasModule --> EventBus
    AuthModule --> ThemeService

    %% Backend connection
    APIClient -.->|REST API| Backend[Backend APIs]
    WebSocketClient -.->|WebSocket| Backend

    %% Styling
    classDef uiNodes fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef coreNodes fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef nodeNodes fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef apiNodes fill:#fff8e1,stroke:#ff8f00,stroke-width:2px
    classDef utilityNodes fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef backendNodes fill:#f5f5f5,stroke:#616161,stroke-width:2px,stroke-dasharray: 5 5

    class AuthUI,Dashboard,CanvasUI,SettingsUI uiNodes
    class AuthModule,CanvasModule,NodeLibraryModule,TracesModule,ConfigModule coreNodes
    class NodeEditor,AgenticTools,SubgraphConfig,GraphConfig,NodeRegistry nodeNodes
    class APIClient,WebSocketClient,AuthService,WorkflowService,NodeService apiNodes
    class ValidationService,CacheService,EventBus,NotificationService,ThemeService utilityNodes
    class Backend backendNodes
```
