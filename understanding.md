# Understanding Your Blood Donor System — A Beginner's Guide

This document explains **what you built, why each piece exists, and how they talk to each other** — written for someone who had never touched AWS Console before this project. Read it top to bottom once, then keep it as a reference.

---

## 1. The Problem We Were Solving

You wanted an app where anyone can open a webpage and add, view, edit, or delete blood donor records — **without you running or maintaining a server yourself.**

That last part — "without maintaining a server" — is the whole reason this project looks the way it does. There are two broad ways to build a web app that stores data:

| Traditional server | Serverless (what we built) |
|---|---|
| You rent a computer (EC2) and keep it running 24/7 | AWS runs tiny bits of your code only when needed |
| You install and patch an OS, a database, a web server | AWS manages all of that invisibly |
| You pay even while nobody is using the app | You pay only for actual requests/storage used |
| One process crash can take the whole app down | Each request is isolated; failures don't cascade |

For a small project like a donor registry, serverless is simpler to reason about **once you understand the pieces** — even though, as you experienced, wiring those pieces together the first time involves a lot of careful clicking.

---

## 2. The Four Building Blocks

```
┌─────────────┐      ┌──────────────┐      ┌─────────┐      ┌──────────┐
│   Browser    │─────▶│ API Gateway  │─────▶│ Lambda  │─────▶│ DynamoDB │
│ (S3 website) │      │              │      │         │      │          │
│              │◀─────│              │◀─────│         │◀─────│          │
└─────────────┘      └──────────────┘      └─────────┘      └──────────┘
   "storefront"        "receptionist"        "waiter"       "filing cabinet"
```

### S3 (Simple Storage Service) — the storefront window
S3 is a place to store files. Nothing more. When we "enabled static website hosting," we just told S3: "if someone asks for `/`, hand them `index.html`." S3 has **no ability to run code** — all the logic in your app (the form, the fetch calls) is JavaScript that runs *inside the visitor's own browser*, not on AWS.

### API Gateway — the receptionist
Lambda functions have no public web address of their own — think of Lambda as a chef working in a kitchen with no door to the street. API Gateway is the receptionist standing at that door: it listens on a real HTTPS URL, checks whether the incoming request matches a route you've defined (like `GET /donor` or `POST /donor`), and if so, wakes up the right Lambda function and hands it the request.

### Lambda — the waiter
Lambda runs your Python code (`lambda_function.py`) **on demand**. It doesn't sit around waiting — AWS spins up a temporary environment to run your function only when a request arrives, then shuts it down afterward. This is why you only pay per request, not for idle time. Your one Lambda function handles *all* the different actions (list, create, get one, update, delete) by checking `httpMethod` and the path inside the code.

### DynamoDB — the filing cabinet
DynamoDB is a NoSQL database — think of it as a giant filing cabinet where every folder (called an "item") is looked up by one key (the "partition key"). We chose `donorId` as that key. Unlike a spreadsheet-style SQL database, DynamoDB doesn't enforce a fixed set of columns — each item can have different fields, though in practice our Lambda code always writes the same shape (fullName, bloodGroup, phone, etc.).

---

## 3. Tracing One Click, Start to Finish

Let's follow exactly what happens when you click **"Add Donor"** in the browser — this single action touches every piece we built.

**Step 1 — Browser → S3 (already happened, before you even click anything)**
When you first opened the website URL, your browser downloaded `index.html`, `app.js`, and `config.js` from the S3 bucket. From this point on, S3 is out of the picture — everything else happens between your browser and the API.

**Step 2 — You fill the form and click "Add Donor"**
JavaScript inside `app.js` reads what you typed, packages it into a JSON object, and calls:
```js
fetch(`${API_URL}/donor`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload),
});
```
`API_URL` here is the value you pasted into `config.js` — your API Gateway's Invoke URL.

**Step 3 — Browser → API Gateway**
Your browser sends a real HTTPS request out to the internet, landing at API Gateway. But first, because your webpage's origin (the S3 URL) is *different* from the API's origin, your browser does a security check called a **CORS preflight** — it silently sends an `OPTIONS` request first, asking "is this cross-origin request allowed?" API Gateway answers yes (because we enabled CORS), and only then does your browser send the real `POST` request.

**Step 4 — API Gateway → Lambda**
API Gateway sees the route `POST /donor` matches what we configured, and — because we checked **"Lambda proxy integration"** — it forwards the *entire* raw request (method, headers, body, everything) to Lambda as one big JSON object called `event`, without trying to reshape it.

**Step 5 — Lambda runs your code**
Inside `lambda_function.py`, the `lambda_handler` function reads `event["httpMethod"]` (sees `"POST"`), sees there's no `donorId` in the path, and calls `create_donor(body)`. That function validates the fields, generates a random `donorId` (a UUID), and calls:
```python
table.put_item(Item=item)
```

**Step 6 — Lambda → DynamoDB**
This is the actual database write. `boto3` (AWS's Python toolkit) sends the request to DynamoDB, which stores your new donor record under the `sanjog_donors` table.

**Step 7 — The return trip**
DynamoDB confirms success → Lambda builds a JSON response (donor data + a 201 status code) → API Gateway passes it straight back (again, because of proxy integration, no reshaping) → your browser's `fetch()` call resolves → `app.js` updates the on-screen list to show the new donor.

All of that — seven steps across four separate AWS services — happens in well under a second.

---

## 4. Why Every Error We Hit, Happened

Looking back at the debugging we did, nearly everything falls into **two categories**. Once you can spot which category an error belongs to, AWS debugging gets much faster.

### Category A — Naming / identity mismatches

AWS is extremely literal. Nothing is auto-corrected or inferred.

| What happened | Why |
|---|---|
| "Table name already exists" | You'd created a table earlier with that exact name |
| Wrong partition key (`sanjog_donors` instead of `donorId`) | Typed into the wrong field on the create-table form |
| `{donorId}` had to be typed exactly (not `{donorID}` or `{id}`) | Your Lambda code does `event['pathParameters']['donorId']` — a different spelling means Python looks for a key that doesn't exist |

**Lesson:** whenever two AWS resources need to refer to the same thing (a table name, a path parameter, a function name), they must match **character-for-character**, including case.

### Category B — Missing explicit permission

AWS's default posture is "deny everything." Every single connection between two services must be explicitly granted — nothing is trusted automatically, even between your own resources.

| What happened | Why |
|---|---|
| Lambda had no DynamoDB access at first | A fresh Lambda role only gets CloudWatch logging permission by default — you must manually attach an inline policy granting DynamoDB actions |
| CORS errors in the browser console | Lambda proxy integrations don't add CORS headers automatically — you must explicitly enable CORS per resource in API Gateway |
| "Grant API Gateway permission to invoke your Lambda function" popup | API Gateway itself needs permission to call your Lambda — accepting that popup writes a resource policy on the Lambda side |

**Lesson:** if something "should obviously work" but silently fails or returns `AccessDenied`, ask "did I explicitly grant this connection permission?" before anything else.

---

## 5. Key AWS Concepts, Explained Simply

**Region** — A physical cluster of data centers (e.g. `us-east-1` = Northern Virginia). Every resource you create lives in exactly one region, and the console only shows you resources in the currently-selected region. Mixing regions by accident is a classic beginner trap.

**IAM Role** — A "keychain" of permissions that an AWS service (like Lambda) wears while running. A role starts empty except for whatever AWS auto-attaches (in our case, basic logging). You add more keys (policies) to the keychain as needed.

**IAM Policy** — A written JSON statement describing exactly what actions are allowed on exactly which resources. We used an *inline policy* (attached directly to one role) rather than a reusable *managed policy*, since we only needed this permission in one place.

**ARN (Amazon Resource Name)** — AWS's universal "full address" for any resource, e.g.
`arn:aws:dynamodb:us-east-1:201962984039:table/sanjog_donors`
Reading left to right: service (`dynamodb`), region, account ID, and the specific resource path. Anytime AWS asks you to "specify a resource," it usually wants an ARN like this.

**Partition Key** — The field DynamoDB uses to physically locate and retrieve an item, similar to a primary key in a SQL database. Once a table is created, the partition key's name **cannot be changed** — this is why we had to delete and recreate the table when it was misconfigured.

**On-demand vs. Provisioned capacity** — On-demand means "charge me per request, no planning needed." Provisioned means "I'll tell you how much read/write throughput to reserve in advance." On-demand is simpler and safer for unpredictable, low-traffic apps like this one.

**Lambda Proxy Integration** — A setting that tells API Gateway "don't transform the request or response, just pass it through raw." Your Lambda code reads the HTTP method and body directly from the `event` object. This is the single most common thing beginners forget to check, since without it, `event['httpMethod']` would come back empty.

**CORS (Cross-Origin Resource Sharing)** — A browser security rule that blocks a webpage from one origin (domain) from calling an API on a different origin, unless the API explicitly allows it via response headers. This has nothing to do with your backend logic being wrong — it's purely a browser-enforced permission check.

**Deploying an API** — In API Gateway, every change you make (new resource, new method, CORS) only exists in a *draft* configuration until you click "Deploy API." Deploying takes a snapshot of your current draft and publishes it to a named "stage" (like `dev`), which is what actually gets a public Invoke URL.

---

## 6. The Full List of Gotchas You Personally Debugged

You hit and correctly resolved every one of these — worth remembering, because they're extremely common beginner traps:

1. **Table name collision** — a table called `Donors` already existed; renamed to `sanjog_donors`.
2. **Wrong partition key** — first attempt had the partition key named `sanjog_donors` instead of `donorId`; had to delete and recreate.
3. **Function name collision** — same issue as #1, but for Lambda; renamed to `sanjog-blood-donor-function`.
4. **IAM ARN builder confusion** — the "Specify ARNs" modal kept defaulting to an index-shaped ARN instead of a table-shaped one; fixed by using the Text tab and targeting the correct "table" row specifically.
5. **"Any in this account" checkbox** — accidentally left checked, which would have granted access to *every* DynamoDB table, not just yours; caught and unchecked before creating the policy.
6. **PowerShell vs. Bash syntax** — the guide's curl commands assumed Bash/Mac syntax; had to translate variable assignment, quoting, and eventually switch to PowerShell's native `Invoke-RestMethod` to avoid Windows' argument-parsing quirks entirely.
7. **CORS on both resources** — had to remember to enable it on *both* `/donor` and `/donor/{donorId}` separately, not just once.
8. **Forgetting to redeploy** — API Gateway changes don't go live until you explicitly click "Deploy API" again after each batch of changes.

---

## 7. What You'd Change for a "Real" Production App

This project is a genuinely solid learning deployment, but if it were going to serve real donors instead of being a demo, here's what would typically change — good to know for context, not something you need to do now:

- **Authorization**: currently `None` — anyone can call any endpoint. A real app would add Amazon Cognito (user login) or API keys.
- **HTTPS on the frontend**: the S3 website endpoint only serves plain HTTP. Adding CloudFront (a CDN) in front of it would give you a free SSL certificate and a proper `https://` URL.
- **Infrastructure as Code**: everything here was built by hand-clicking through the console. A production team would define this same setup in a CloudFormation, SAM, or Terraform file, so it can be recreated identically with one command instead of by hand.
- **Environments**: you'd typically have separate `dev` and `prod` stages/tables, so testing doesn't touch real data.
- **Monitoring/Alarms**: CloudWatch alarms on Lambda errors or DynamoDB throttling, so you're notified if something breaks.

None of these are needed for what you built today — they're just the natural "next steps" if this project ever grew beyond a learning exercise.

---

## 8. Quick Reference — Your Actual Resource Names

| Resource | Name |
|---|---|
| DynamoDB table | `sanjog_donors` |
| Lambda function | `sanjog-blood-donor-function` |
| API Gateway API | `sanjog-blood-donor-api` |
| API stage | `dev` |
| S3 bucket | `sanjog-blood-donor-frontend-201962984039` |
| GitHub repo | `github.com/SanjogGautam/blood-donor-system` |
| Region | `us-east-1` (N. Virginia) |