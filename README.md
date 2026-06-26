# Guardian AI

**A Secure AI-Powered Surveillance and Crime Analysis System**

---

## Overview

Guardian AI is a secure, intelligent platform designed to support law enforcement agencies in crime monitoring and risk assessment. The system integrates machine learning with modern cybersecurity practices to deliver a reliable and scalable solution for incident management and predictive analytics.

---

## Features

- **Crime Risk Prediction** — XGBoost classifier analyzes historical crime data to predict risk levels (Low / Medium / High)
- **AI Chatbot** — Natural language interface for querying crime data and generating insights
- **Analytics Dashboard** — Visual representation of crime trends, statistics, and hotspot analysis
- **JWT Authentication** — Secure, token-based user authentication
- **Role-Based Access Control (RBAC)** — Distinct access levels for Admin, Analyst, and Viewer roles
- **AES-256 Encryption** — Encryption of sensitive suspect and case data
- **CSRF Protection & Rate Limiting** — Defense against common web-based attacks
- **Audit Logging** — Comprehensive logging of all user actions and system events

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite), Tailwind CSS |
| Backend | Python, Flask |
| Machine Learning | XGBoost, Scikit-learn |
| Security | JWT, bcrypt, AES-256 |
| Database | SQLite / PostgreSQL |

---

## Installation

### Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The application will be accessible at `http://localhost:5173`.

---

## Environment Configuration

Create a `.env` file in the `/backend` directory with the following variables:

```
SECRET_KEY=your_jwt_secret_key
AES_KEY=your_aes_encryption_key
DATABASE_URL=sqlite:///guardian.db
```

---

## Project Structure

```
guardian-ai/
├── backend/
│   ├── app.py
│   ├── routes/          # Authentication, prediction, chatbot, admin
│   ├── ml/              # ML pipeline and versioned model artifacts
│   └── security/        # JWT handling, AES encryption, audit logging
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── api/
└── README.md
```

---

## Developer

**Fatima Hameed**
University of Engineering and Technology (UET)

---

> Developed for academic purposes as part of the Computer Science program at UET.
