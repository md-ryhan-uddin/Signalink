# 🚀 Signalink - Distributed Real-Time Messaging System

**A learning-focused, production-inspired real-time messaging and notification system**

Signalink is a technology laboratory designed to teach modern distributed systems, backend architecture, cloud deployment, and DevOps through hands-on experience.

---

## 📖 Project Overview

Signalink is **NOT** a full Slack clone. It's a comprehensive learning platform covering:

- ✅ Event-driven distributed architecture
- ✅ Real-time messaging with WebSockets
- ✅ In-memory caching and pub/sub (Redis)
- ✅ Message brokering with Kafka
- ✅ Database design and persistence (PostgreSQL)
- ✅ Cloud deployment (AWS Free Tier)
- ✅ Observability and monitoring
- ✅ CI/CD automation

---

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
┌──────▼────────┐
│  API Gateway  │
└──────┬────────┘
       │
   ┌───┴────┐
   │        │
┌──▼──┐  ┌──▼────────┐
│ API │  │ WebSocket │
└──┬──┘  └─┬─────────┘
   │       │
┌──▼───┐ ┌▼────┐
│ DB   │ │Redis │
└──────┘ └┬─────┘
          │
      ┌───▼────┐
      │ Kafka  │
      └───┬────┘
          │
    ┌─────┴──────┐
    │            │
┌───▼─────┐  ┌───▼────────┐
│Analytics│  │Notification│
└─────────┘  └────────────┘
```

---

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15
- **Cache/Pub-Sub**: Redis 7
- **Message Broker**: Apache Kafka (AWS MSK Serverless)
- **Authentication**: JWT

### DevOps & Cloud
- **Containerization**: Docker, docker-compose
- **Cloud**: AWS (EC2, API Gateway, MSK, RDS)
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus, Grafana, CloudWatch

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Git

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Signalink
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your configuration. For local development, the defaults should work.

### 3. Start Services with Docker Compose

```bash
# Start Phase 1 & 2 & 3 services (API + WebSocket + PostgreSQL + Redis + Kafka + Zookeeper)
docker-compose --profile phase2 --profile phase3 up -d

# OR start only Phase 1 & 2 services (without Kafka)
docker-compose --profile phase2 up -d

# OR start only Phase 1 services (API only)
docker-compose up -d

# View logs
docker-compose logs -f api-signalink
docker-compose logs -f websocket-signalink
docker-compose logs -f kafka-signalink

# Stop services
docker-compose down
```

### 4. Access the Services

- **REST API Docs (Swagger)**: http://localhost:8000/docs
- **Alternative Docs (ReDoc)**: http://localhost:8000/redoc
- **REST API Health Check**: http://localhost:8000/health
- **WebSocket Service**: ws://localhost:8001/ws?token=YOUR_JWT_TOKEN
- **WebSocket Stats**: http://localhost:8001/stats

---

## 📋 Current Status: Phase 3 ✅

**Phase 1: Foundation & REST API** - **COMPLETED**
**Phase 2: WebSocket Real-Time Messaging** - **COMPLETED**
**Phase 3: Kafka Event Streaming** - **COMPLETED**

### What's Implemented

#### Phase 1: REST API & Database
- ✅ Project structure and Docker setup
- ✅ FastAPI REST API service
- ✅ PostgreSQL database schema with migrations
- ✅ JWT authentication system
- ✅ User registration and login endpoints
- ✅ Channel CRUD operations
- ✅ Message persistence endpoints
- ✅ Role-based access control

#### Phase 2: Real-Time Communication
- ✅ FastAPI WebSocket service
- ✅ Redis pub/sub for message broadcasting
- ✅ Real-time message delivery
- ✅ User presence tracking (online/offline/away)
- ✅ Typing indicators
- ✅ Multi-device support per user
- ✅ Connection health monitoring (ping/pong)

#### Phase 3: Event Streaming
- ✅ Kafka 7.5.0 + Zookeeper infrastructure
- ✅ 4 Kafka topics (messages, notifications, analytics, presence)
- ✅ Async Kafka producer integration
- ✅ Multi-topic Kafka consumer
- ✅ Event-driven architecture with Pydantic schemas
- ✅ 6 event handlers for message operations
- ✅ FastAPI lifecycle management for Kafka
- ✅ Comprehensive integration test suites

### Available Endpoints

#### Authentication & Users
- `POST /api/v1/users/register` - Register new user
- `POST /api/v1/users/login` - Login and get JWT token
- `GET /api/v1/users/me` - Get current user profile
- `PUT /api/v1/users/me` - Update user profile
- `GET /api/v1/users/{username}` - Get user by username
- `GET /api/v1/users/` - Search users

#### Channels
- `POST /api/v1/channels/` - Create channel
- `GET /api/v1/channels/` - List accessible channels
- `GET /api/v1/channels/{channel_id}` - Get channel details
- `PUT /api/v1/channels/{channel_id}` - Update channel
- `DELETE /api/v1/channels/{channel_id}` - Delete channel
- `POST /api/v1/channels/{channel_id}/members` - Add member
- `GET /api/v1/channels/{channel_id}/members` - List members
- `DELETE /api/v1/channels/{channel_id}/members/{user_id}` - Remove member

#### Messages
- `POST /api/v1/messages/` - Send message
- `GET /api/v1/messages/channels/{channel_id}` - Get channel messages
- `GET /api/v1/messages/{message_id}` - Get specific message
- `PUT /api/v1/messages/{message_id}` - Update message
- `DELETE /api/v1/messages/{message_id}` - Delete message

---

## 🧪 Testing the API

### Using Swagger UI

1. Navigate to http://localhost:8000/docs
2. Register a user via `POST /api/v1/users/register`
3. Login via `POST /api/v1/users/login` to get token
4. Click "Authorize" button and paste token
5. Test other endpoints

### Using cURL

```bash
# Register a user
curl -X POST http://localhost:8000/api/v1/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "securepass123",
    "full_name": "Test User"
  }'

# Login
curl -X POST http://localhost:8000/api/v1/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "securepass123"
  }'

# Use the token from login response
TOKEN="your-jwt-token-here"

# Create a channel
curl -X POST http://localhost:8000/api/v1/channels/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "engineering",
    "description": "Engineering team channel",
    "is_private": false
  }'

# Send a message
curl -X POST http://localhost:8000/api/v1/messages/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "channel-uuid-here",
    "content": "Hello, Signalink!",
    "message_type": "text"
  }'
```

---

## 📁 Project Structure

```
signalink/
├── services/
│   ├── api/                    # REST API service (Phase 1) ✅
│   │   └── app/kafka/          # Kafka integration (Phase 3) ✅
│   ├── websocket/              # WebSocket service (Phase 2) ✅
│   ├── analytics/              # Analytics microservice (Phase 4) ⬜
│   └── notifications/          # Notification worker (Phase 5) ⬜
├── database/
│   ├── migrations/
│   └── schema.sql              # Database schema ✅
├── tests/
│   ├── unit/
│   ├── integration/            # Phase 1, 2, 3 tests ✅
│   └── load/
├── infrastructure/
│   └── docker/
│       └── docker-compose.yml  # Local development ✅
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
├── docs/
├── .github/workflows/          # CI/CD pipelines ⬜
├── requirements.txt            # Root dependencies ✅
├── docker-compose.yml          # Docker orchestration ✅
├── .env.example                # Environment template ✅
├── .gitignore                  # Git ignore rules ✅
├── README.md                   # This file ✅
└── IMPLEMENTATION_TRACKER.md   # Progress tracking ✅
```

---

## 🎯 Learning Roadmap

### ✅ Phase 1: Foundation & REST API (COMPLETED)
**Skills**: Backend engineering, API design, JWT auth, PostgreSQL
**Completed**: December 5, 2025

### ✅ Phase 2: WebSocket Real-Time Messaging (COMPLETED)
**Skills**: Async programming, WebSockets, Redis pub/sub, connection management
**Completed**: December 7, 2025

### ✅ Phase 3: Kafka Event Streaming (COMPLETED)
**Skills**: Event-driven architecture, message brokers, stream processing, async consumers
**Completed**: December 13, 2025

### ⬜ Phase 4: Analytics Microservice (NEXT)
**Skills**: Stream processing, metrics aggregation, time-series data

### ⬜ Phase 5: Notification Worker
**Skills**: Background workers, async task processing, Firebase integration

### ⬜ Phase 6: Cloud Deployment
**Skills**: AWS deployment, infrastructure as code, CI/CD

### ⬜ Phase 7: Observability & Monitoring
**Skills**: Logging, metrics, tracing, alerting, dashboards

---

## 🔧 Development Commands

```bash
# Start all Phase 1, 2, & 3 services (Full stack)
docker-compose --profile phase2 --profile phase3 up -d

# Start only Phase 1 & 2 services (without Kafka)
docker-compose --profile phase2 up -d

# Start only Phase 1 services (API only)
docker-compose up -d

# View logs
docker-compose logs -f api-signalink
docker-compose logs -f websocket-signalink
docker-compose logs -f kafka-signalink

# Rebuild services after code changes
docker-compose up -d --build api-signalink

# Stop all services
docker-compose down

# Stop and remove volumes (reset database)
docker-compose down -v

# Access PostgreSQL directly
docker exec -it signalink_db psql -U signalink -d signalink

# Access Redis CLI
docker exec -it signalink_redis redis-cli

# Check Kafka topics
docker exec signalink_kafka kafka-topics --bootstrap-server localhost:9092 --list

# Check Kafka consumer groups
docker exec signalink_kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group signalink-consumers --describe
```

---

## 📊 Database Schema

### Core Tables

- **users** - User accounts and authentication
- **channels** - Channel/room information
- **channel_members** - User-channel membership mapping
- **messages** - Message storage with soft delete
- **message_reactions** - Emoji reactions to messages
- **read_receipts** - Read status tracking
- **user_sessions** - JWT session management
- **notification_preferences** - User notification settings
- **analytics_events** - Event tracking for analytics

### Key Features

- UUID primary keys
- Automatic timestamps (created_at, updated_at)
- Soft deletes for messages
- Role-based channel permissions (owner, admin, member)
- JSONB metadata fields for extensibility
- Database triggers for automation
- Optimized indexes for performance

---

## 🧰 Tech Stack Details

### Why These Technologies?

| Technology | Reason | Learning Value |
|------------|--------|----------------|
| **FastAPI** | Modern, async, auto-docs | Async Python, REST API design |
| **PostgreSQL** | ACID compliance, JSON support | SQL, transactions, indexing |
| **Redis** | Low-latency pub/sub | Caching, real-time patterns |
| **Kafka** | Durable event streaming | Event-driven architecture |
| **Docker** | Reproducible environments | Containerization, DevOps |
| **AWS** | Industry-standard cloud | Cloud-native deployment |

---

## 🎓 What You'll Learn

### Backend Engineering
- REST API design and versioning
- Async/await patterns in Python
- JWT authentication and authorization
- Database schema design and optimization

### Distributed Systems
- Event-driven architecture
- Pub/sub messaging patterns
- Stream processing with Kafka
- Microservices communication

### Real-Time Systems
- WebSocket protocols
- Connection management at scale
- Message fanout strategies
- Presence tracking

### Cloud & DevOps
- Docker containerization
- AWS service integration
- CI/CD pipeline automation
- Infrastructure as code

### Observability
- Structured logging
- Metrics collection and visualization
- Distributed tracing
- Alerting and incident response

---

## 🐛 Known Issues & Limitations

### Current Limitations (After Phase 3)

- ✅ Real-time message delivery implemented (Phase 2)
- ✅ Event streaming with Kafka implemented (Phase 3)
- ❌ No analytics dashboard or metrics visualization (Phase 4)
- ❌ No push notifications to mobile devices (Phase 5)
- ❌ Local deployment only, not production-ready (Phase 6)
- ❌ Limited observability and monitoring (Phase 7)

### Future Improvements

- Message search functionality
- File upload support
- Message threading
- @mentions and notifications
- Custom emojis
- Rate limiting per user
- Message encryption

---

## 🤝 Contributing

This is a learning project. Feel free to:

- Experiment with the code
- Try different architectural approaches
- Add features as learning exercises
- Document your learnings

---

## 📚 Resources

### Documentation
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)
- [Redis Pub/Sub](https://redis.io/docs/manual/pubsub/)
- [Apache Kafka](https://kafka.apache.org/documentation/)
- [AWS Free Tier](https://aws.amazon.com/free/)

### Books
- "Designing Data-Intensive Applications" by Martin Kleppmann
- "Building Microservices" by Sam Newman

### Courses
- [System Design Primer](https://github.com/donnemartin/system-design-primer)
- [FastAPI Course](https://testdriven.io/courses/fastapi/)

---

## 📝 License

This is an educational project. Use freely for learning purposes.

---

## 🙏 Acknowledgments

Built for learning distributed systems, backend engineering, and cloud technologies.

**Happy Learning! 🚀**

For detailed implementation progress, see [IMPLEMENTATION_TRACKER.md](IMPLEMENTATION_TRACKER.md)
