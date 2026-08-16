# 🩸 Blood Donor Data Management System

A serverless blood donor registry built on AWS — DynamoDB, Lambda, API Gateway, and a static S3-hosted frontend. No servers to manage, pay only for what you use.

## Architecture

```
Browser (S3 static website)
      │  HTTP requests
      ▼
API Gateway (REST API, stage: dev)
      │  Lambda proxy integration
      ▼
Lambda (Python 3.12)
      │  boto3
      ▼
DynamoDB (Donors table)
```

| Piece | Service | What it does |
|---|---|---|
| Database | DynamoDB | Stores donor records |
| Backend | Lambda (Python 3.12) | One function, routes by HTTP method + path |
| API | API Gateway (REST API) | Exposes `/donor` and `/donor/{donorId}` over HTTPS |
| Frontend | S3 static website | Hosts the HTML/JS app |

## Project structure

```
blood-donor-system/
├── lambda_function.py      # Backend: all CRUD routes
├── frontend/
│   ├── index.html
│   ├── config.js           # Set your API Gateway Invoke URL here
│   └── app.js
└── .gitignore
```

## API routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/donor` | List all donors (optional `?bloodGroup=` filter) |
| POST | `/donor` | Create a new donor |
| GET | `/donor/{donorId}` | Get one donor |
| PUT | `/donor/{donorId}` | Update a donor |
| DELETE | `/donor/{donorId}` | Delete a donor |

## Donor record schema

| Field | Type | Notes |
|---|---|---|
| `donorId` | String | Partition key, server-generated UUID |
| `fullName` | String | Required |
| `bloodGroup` | String | Required; one of A+, A-, B+, B-, AB+, AB-, O+, O- |
| `phone` | String | Required |
| `email` | String | Optional |
| `donationDate` | String (ISO date) | Optional |
| `notes` | String | Optional |
| `createdAt` | String (ISO datetime) | Set on create |
| `updatedAt` | String (ISO datetime) | Set on create and every update |

## Deployment (manual, console-driven)

1. **DynamoDB** — create a table with partition key `donorId` (String), On-demand capacity.
2. **Lambda** — Python 3.12 function, paste in `lambda_function.py`, set environment variable `DONORS_TABLE_NAME` to your table name, and grant the execution role `PutItem`/`GetItem`/`UpdateItem`/`DeleteItem`/`Scan` permissions scoped to that table's ARN.
3. **API Gateway** — REST API with `/donor` and `/donor/{donorId}` resources, GET/POST/PUT/DELETE methods using Lambda proxy integration, CORS enabled on both resources, deployed to a stage (e.g. `dev`).
4. **S3** — static website hosting enabled, public read bucket policy, upload the `frontend/` files after setting `API_URL` in `config.js` to your API Gateway Invoke URL.

## Testing the API directly

```bash
API=https://your-api-id.execute-api.us-east-1.amazonaws.com/dev

curl -X POST "$API/donor" -H "Content-Type: application/json" -d '{
  "fullName": "Asha Rai",
  "bloodGroup": "O+",
  "phone": "+977-9800000000"
}'

curl "$API/donor"
curl "$API/donor?bloodGroup=O%2B"
```

## Notes

- Authorization is set to `None` on all routes — anyone can call this API. Fine for a learning project; add Cognito or IAM auth before using this with real data.
- The frontend is plain HTML/CSS/JS (no build step) — edit `config.js`, then upload all three files directly to S3.

http://sanjog-blood-donor-frontend-201962984039.s3-website-us-east-1.amazonaws.com/