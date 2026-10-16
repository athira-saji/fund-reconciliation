# FundFlow: Capital Call & Bank Reconciliation

## 1. App Overview

**FundFlow** is a multi-tenant fund administration portal that imports bank statement CSV files, matches incoming payments against capital call line items, and supports reconciliation with safeguards against duplicate funding.

## 2. Setup from a Fresh Clone

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- PostgreSQL

### Step 1: Clone the Repository

```bash
git clone https://github.com/athira-saji/fund-reconciliation.git
cd fund-reconciliation
```

### Step 2: Configure the Backend

Navigate to the backend directory:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

On macOS/Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

Create a `.env` file inside `backend/` using `.env.example` as a template.

Example configuration:

```env
DB_NAME=fund_recon_db
DB_USER=postgres
DB_PASSWORD=your_database_password
DB_HOST=localhost
DB_PORT=5432
```

Update the values to match your local PostgreSQL configuration. Create the PostgreSQL database `fund_recon_db` if it does not already exist.

Do not commit `.env` or actual database credentials to version control.

### Step 4: Apply Database Migrations

```bash
python manage.py migrate
```

The repository should include its migration files. Running `makemigrations` is only necessary if new model changes have not yet been captured in migrations.

### Step 5: Seed Demo Data

```bash
python manage.py seed_demo
```

This command populates the database with demo organizations, capital calls, investor entities, and capital call line items.

### Step 6: Run the Backend Tests

From the `backend/` directory, execute the test suite:

```bash
python manage.py test reconciliation
```

This is the single command to run the reconciliation tests.

### Step 7: Start the Backend

```bash
python manage.py runserver 8000
```

The backend runs at `http://127.0.0.1:8000/`.

### Step 8: Start the Frontend

Open a second terminal from the repository root:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173/`.

The Vite development server proxies `/api` requests to the Django backend.

## 3. Environment Variables

The repository includes `backend/.env.example` with placeholder database configuration. No real credentials should be included in the example file.

## 4. Data Model

- **Organization:** Defines the tenant boundary, identified by a unique slug.
- **BankTransaction:** Stores imported bank transactions, including the date, description, Decimal amount, transaction type (credit or debit), bank reference, and reconciliation status. Bank references are unique within each organization.
- **InvestorEntity:** Stores investor entities associated with an organization.
- **CapitalCall:** Represents a capital call event belonging to an organization, with an identifier, call date, and due date.
- **CapitalCallLineItem:** Links a capital call to an investor entity and tracks the expected reference, amount called, amount funded, remaining balance, and funding status (`open`, `partially_funded`, or `funded`).
- **MatchSuggestion:** Records proposed matches between bank transactions and capital call line items, including the match rationale and status (`proposed`, `approved`, or `rejected`).

## 5. API Endpoints

All endpoints are defined under the `/api/` prefix.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/transactions/` | Lists bank transactions with their associated match suggestions. |
| POST | `/api/transactions/upload/` | Uploads and parses a bank statement CSV file. |
| POST | `/api/transactions/<transaction_id>/ignore/` | Marks a transaction as ignored. |
| POST | `/api/matches/<match_id>/confirm/` | Confirms a proposed match and updates the funded amount. |
| POST | `/api/matches/<match_id>/reject/` | Rejects a proposed match. |
| GET | `/api/capital-call-items/` | Lists capital call line items. |

The active organization is specified through the `X-Organization` request header.


## 6. Assumptions and Trade-offs

- Reference numbers are checked first, with investor name and amount used as a fallback when no reference match is found.
- Partial payments are supported, but the funded amount cannot exceed the amount called.
- Duplicate transactions are identified using the bank reference within each organization.
- Authentication is outside the scope of this assessment. The `X-Organization` header is used to select the organization.

## 7. Potential Next Steps

- Add authentication and restrict access to each user's organization.
- Expand API tests and add end-to-end tests for key workflows.
- Add audit logging to track reconciliation decisions and changes.
- Deploy the application with production-ready configuration and database setup.

## 8. Integrity Statement

> I completed this assessment without using AI assistance.