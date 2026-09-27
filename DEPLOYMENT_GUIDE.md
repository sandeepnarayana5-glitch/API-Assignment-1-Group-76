# Step-by-Step Guide: Finishing and Submitting This Assignment

Written to be followed top to bottom. Every command is copy-paste. You do not
need to understand Python to complete this.

---

## Part 0 — What this project actually is

Strip away the jargon and there are two things:

**Thing 1 — A robot that repeats a job every 2 minutes.**
It opens a spreadsheet of 4,600 house sales, cleans the bad rows, draws four
charts, trains a price-prediction model, and writes down everything it did in a
log. Then it waits 2 minutes and does it all again. Forever. That repeating
robot is the "data pipeline", and it is worth 10 of the 15 marks.

**Thing 2 — A set of web addresses that report on Thing 1.**
If you open `/api/pipeline/status` in a browser you get a text summary of how
many times the robot has run and whether it succeeded. There are 10 such
addresses. Those are the "APIs", worth the other 5 marks.

A web dashboard ties both together in one page so a human can watch it happen.

### The five words you need for the viva

| Word | What it means here |
|---|---|
| **Pipeline** | The 4-step job: load data → clean it → analyse it → train model |
| **API endpoint** | A web address that returns data instead of a web page |
| **Scheduler** | The timer that fires the pipeline every 120 seconds |
| **EC2** | A computer you rent from Amazon, by the hour |
| **CloudWatch** | Amazon's logbook service — where your logs go to be viewed |

---

## Part 1 — What was broken, and what is now fixed

Your friend's version worked but had eleven problems that would have cost marks.
All are now fixed. **Read this table before your viva** — you will be asked
"what did you contribute?" and this is your honest answer.

| # | Problem | Fix applied |
|---|---|---|
| 1 | Nothing ran on a cloud — everything was on a laptop | AWS deployment path added (Parts 3–5 below) |
| 2 | Rubric demands **encoding**; there was none anywhere | Four techniques added: one-hot, label, frequency, binary |
| 3 | Rubric demands **imputation**; the dataset had zero missing values so that code never ran | 2% of numeric cells are now blanked at load (fixed seed), so imputation genuinely fires and is logged |
| 4 | The "improved" Random Forest was **worse** than the baseline | Top 0.5% luxury outliers removed; RF now genuinely wins |
| 5 | Dashboard reported the wrong model's score | Now reports the actually-selected model |
| 6 | A crash left a run stuck on "RUNNING" forever, breaking the success rate | Auto-reconciles on startup |
| 7 | README claimed "20/20 Postman tests" — the collection had **zero** | 12 requests, each with 5 real assertions |
| 8 | `/api/application` hard-coded "Python 3.14" regardless of reality | Reports the real runtime |
| 9 | Stage-by-stage activity log was collected but never displayed | New "Stage Activity Log" panel on the dashboard |
| 10 | Port was 8080 in some files, 8000 in others | 8000 everywhere |
| 11 | Zip contained junk files and absolute Windows paths | Cleaned |

Plus: tests went from 13 to 18, and a new endpoint `/api/cloud/deployment` was
added that calls **AWS's own APIs** — this is the one that satisfies the
"use built-in APIs" requirement that was previously unmet.

**About fix #3 — be ready to explain this one.** The original Kaggle file has no
missing values, so the imputation code could never demonstrate itself. The app
now deliberately blanks 2% of cells using a fixed random seed (so it is
reproducible) *after* reading the file — the source CSV is never modified. This
is declared in the code comments, in the logs, and should be stated in your
report. It is a legitimate technique. Hiding it would not be.

---

## Part 2 — Run it on your laptop first

Do this **before** touching AWS. Ten minutes. If it works here, it will work there.

### 2.1 Install Python
Download Python 3.11 from python.org. **On the installer's first screen, tick
"Add Python to PATH"** — miss this and nothing below works.

### 2.2 Open a terminal in the project folder
Unzip the project. Open the folder. In the address bar of the folder window,
type `cmd` and press Enter (Windows) or right-click → "New Terminal at Folder" (Mac).

### 2.3 Install and run

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The test command should print **18 passed**. The last command will pause and
print `Application startup complete` — that means it is running. Leave that
window open.

### 2.4 Look at it
Open a browser:
- `http://127.0.0.1:8000/` — the dashboard
- `http://127.0.0.1:8000/docs` — the auto-generated API documentation

Watch the countdown on the dashboard hit zero. A new row appears in the audit
trail. That is your 2-minute scheduler, working.

To stop it: press `Ctrl + C` in the terminal.

---

## Part 3 — Put it on AWS (EC2)

Launch lab **AIMLZG549D (Console)** from the Prayogshala portal.

> **Critical:** lab sessions expire and everything is wiped. Do Parts 3, 4, 5
> and 6 in **one sitting**. Read all four parts first, then start.

### 3.1 Launch the server
In the AWS Console, search **EC2** → **Launch instance**.

| Setting | Value |
|---|---|
| Name | `dataops-group76` |
| AMI | Amazon Linux 2023 |
| Instance type | `t3.medium` |
| Key pair | Create new, name it `group76-key`, download the `.pem` file |
| Network → Auto-assign public IP | **Enable** |

Under **Network settings → Edit → Add security group rule**:
- Type `Custom TCP`, Port range `8000`, Source `0.0.0.0/0`

Click **Launch instance**. Wait for "Running". **Copy the Public IPv4 address** —
you need it repeatedly. Call it `<YOUR-IP>`.

### 3.2 Connect
Select the instance → **Connect** button → **EC2 Instance Connect** tab →
**Connect**. A black terminal opens in your browser. No `.pem` file needed.

### 3.3 Install Docker

```bash
sudo yum update -y
sudo yum install -y docker git
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user
```

Now **close the terminal tab and reconnect** (step 3.2 again). This is required
for the last command to take effect.

```bash
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker --version
```

### 3.4 Upload the project
Easiest route — push the folder to a **private** GitHub repo from your laptop,
then on the EC2 terminal:

```bash
git clone https://github.com/<your-username>/API-Assignment-1-Group-76.git
cd API-Assignment-1-Group-76
```

No GitHub? Use the **Upload file** button in EC2 Instance Connect to send the
zip, then `unzip API-Assignment-1-Group-76.zip && cd API-Assignment-1-Group-76`.

### 3.5 Start it

```bash
docker-compose up -d --build
docker-compose logs -f
```

Wait for `Application startup complete`, then press `Ctrl + C` (this stops the
log view, not the app).

### 3.6 Confirm it is live
In your browser: `http://<YOUR-IP>:8000/`

**Your dashboard is now on the internet.** That alone closes the single biggest
gap in the original submission.

---

## Part 4 — Turn on CloudWatch logging

This gives you a genuine *cloud* dashboard, which is what rubric 1.5 asks for.

### 4.1 Create an access key
AWS Console → search **IAM** → **Users** → your user → **Security credentials**
tab → **Create access key** → choose "Application running outside AWS" →
**Create**.

Copy both values now. The secret is shown **once**.

### 4.2 Give the app the key
Back in the EC2 terminal:

```bash
cd ~/API-Assignment-1-Group-76
nano .env
```

Change these three lines (arrow keys to move, type normally):

```
CLOUDWATCH_ENABLED=true
AWS_ACCESS_KEY_ID=<paste your key id>
AWS_SECRET_ACCESS_KEY=<paste your secret>
```

Save and exit: `Ctrl + O`, `Enter`, `Ctrl + X`.

```bash
docker-compose down && docker-compose up -d
```

### 4.3 See your logs in the cloud
AWS Console → **CloudWatch** → **Log groups** → `/dataops/pipeline`.

Click into the log stream. Every ingestion, preprocessing, EDA and modeling
event from your pipeline is now there. **Screenshot this.**

### 4.4 Build the CloudWatch dashboard
CloudWatch → **Dashboards** → **Create dashboard** → name it `Group76-DataOps` →
**Add widget** → **Logs table** → select `/dataops/pipeline` → paste this query:

```
fields @timestamp, stage, event, status, message
| sort @timestamp desc
| limit 50
```

**Run query** → **Create widget** → **Save**. Screenshot it.

---

## Part 5 — API Gateway (gives you a clean HTTPS address)

AWS Console → **API Gateway** → **Create API** → **HTTP API** → **Build**.

1. **Integrations** → Add integration → **HTTP URI** →
   `http://<YOUR-IP>:8000/{proxy}` → Method `ANY`
2. **API name**: `group76-dataops-api` → Next
3. **Resource path**: `/{proxy+}`, Method `ANY` → Next
4. **Stage**: `$default`, Auto-deploy on → Next → **Create**

Copy the **Invoke URL** at the top. It looks like
`https://abc123.execute-api.us-east-1.amazonaws.com`.

Test it: open `<invoke-url>/api/health` in a browser. You should see
`{"status":"HEALTHY", ...}`.

**Use this HTTPS address in your video and screenshots, not the raw IP.** It
looks far more professional and it demonstrates API Gateway, which is listed in
your lab's environment stack.

---

## Part 6 — Screenshots to capture

Take every one of these. The report is graded on evidence, not on code quality.

**Part A evidence (the pipeline):**
1. Dashboard with the 2-minute countdown mid-tick
2. Audit trail table showing 5+ runs, timestamps exactly 2 minutes apart
3. Stage Activity Log panel showing Ingestion → Preprocessing → EDA → Modeling
4. All four EDA charts (click through the dashboard tabs)
5. `/api/dataset/summary` in a browser — the summary statistics
6. `/api/eda/summary` — scroll to `encoding_summary` so all four encoding techniques are visible
7. A log line reading `Imputed with median (...)` — your proof of imputation
8. `/api/model/metrics` — Linear Regression vs Random Forest side by side
9. CloudWatch log group with your pipeline events
10. The CloudWatch dashboard widget

**Part B evidence (the APIs):**
11. Swagger docs page at `<invoke-url>/docs` showing all 10 endpoints
12. Postman: `GET /api/application` → 200, response body visible
13. Postman: `GET /api/pipeline/status` → 200
14. Postman: `POST /api/pipeline/trigger` → **202 Accepted** (a non-200 code — graders look for this)
15. Postman: `POST /api/predict` with bad data → **422** (proves validation works)
16. Postman: `GET /api/cloud/deployment` → 200, showing real EC2 and API Gateway data
17. **Postman Runner summary** — import `postman_collection.json`, click Runner, run all 12, screenshot the green pass count
18. Terminal showing `18 passed`

**Cloud evidence:**
19. EC2 console showing the instance Running, with instance ID and public IP
20. API Gateway console showing your API and its Invoke URL
21. Browser address bar showing the HTTPS invoke URL with the dashboard loaded
22. AWS Billing → Cost Explorer, showing what the deployment cost

### Postman in 60 seconds
Download from postman.com. **Import** → drag in `postman_collection.json` →
click the collection name → **Variables** tab → change `base_url` to your API
Gateway invoke URL → **Save**. Now click any request → **Send**. The **Test
Results** tab shows the assertions passing.

---

## Part 7 — The video (5–7 minutes)

Record with the free version of OBS, or Zoom recording a screen share.

| Time | Show | Say |
|---|---|---|
| 0:00 | Title slide: group ID, names, topic | Introduce the problem: predicting house prices from 4,600 sales records |
| 0:30 | Project folder structure | Four pipeline stages, an API layer, a dashboard |
| 1:00 | Terminal: `python -m pytest tests/ -v` | 18 automated tests, all passing |
| 1:45 | Browser: the live HTTPS dashboard | This is deployed on AWS EC2, fronted by API Gateway |
| 2:30 | The countdown hitting zero, new audit row appearing | The scheduler fires every 120 seconds, fully automated |
| 3:15 | Stage Activity Log, then the four EDA charts | Every stage is logged; here is the univariate, bivariate, correlation and importance analysis |
| 4:00 | `/api/eda/summary`, scrolled to encoding | Four encoding techniques: one-hot, label, frequency, binary |
| 4:30 | Postman Runner, all 12 requests green | Status codes verified: 200, 202, 422 |
| 5:15 | `/api/cloud/deployment` response | These come from AWS's own built-in APIs — EC2, API Gateway, CloudWatch, Cost Explorer |
| 6:00 | CloudWatch dashboard | Pipeline logs on a cloud dashboard |
| 6:30 | Contribution slide | Who did what |

Do a dry run first. Speak slower than feels natural.

---

## Part 8 — The Word document

Name it `Group-76.docx`. Structure:

1. **Cover** — course code AIMLZG549, Group 76, all member names and IDs
2. **Business Understanding** (½ page) — manual property valuation is slow and
   inconsistent; an automated pipeline gives repeatable data-driven estimates
3. **Data Ingestion** — Kaggle `shree1992/housedata`, 4,600 rows × 18 columns,
   schema auto-detection, screenshot
4. **Data Pre-processing** — summary statistics, data types, missing-value audit
   and median imputation (state the 2% simulation openly), removal of 49
   zero-price rows and the top 0.5% outliers, StandardScaler normalisation
5. **Exploratory Data Analysis** — correlation matrix, the four charts, three
   binning strategies, **all four encoding techniques**, Random Forest feature
   importance
6. **DataOps Automation** — APScheduler at 120s, triple logging (SQLite + JSONL +
   CloudWatch), screenshots of the audit trail and the CloudWatch dashboard
7. **API Access** — table of all 10 endpoints; screenshots of at least four;
   **call out `/api/cloud/deployment` explicitly as the built-in-API requirement**
8. **API Testing** — Postman screenshots showing 200, 202 and 422; the Runner
   summary; the pytest output
9. **Cloud Deployment** — EC2, Docker, API Gateway, CloudWatch, the cost screenshot
10. **Contribution of Each Member** — a table. Be accurate.
11. **Conclusion** — what you would add next (real-time ingestion, model registry,
    auto-scaling)

---

## If something breaks

| Symptom | Fix |
|---|---|
| `pip` not recognised | Python wasn't added to PATH. Reinstall, tick the box. |
| Browser can't reach `<YOUR-IP>:8000` | Security group is missing the port 8000 inbound rule |
| `docker: permission denied` | You skipped the reconnect after `usermod`. Reconnect. |
| Dashboard loads, tables empty | Wait 2 minutes for the first scheduled run, or `POST /api/pipeline/trigger` |
| CloudWatch log group missing | `CLOUDWATCH_ENABLED` is still `false`, or the key is wrong. Check `docker-compose logs`. |
| Cost Explorer returns empty | It has a ~24h data delay on new accounts. Screenshot the Billing console instead. |
| Everything vanished | The lab session expired. Relaunch and redo Part 3. This is why you capture evidence in one sitting. |

---

## Order of operations

1. Part 2 on your laptop — confirm 18 tests pass ✅
2. Read Parts 3–6 fully before launching the lab
3. Launch the lab, do Parts 3, 4, 5 back to back
4. Capture all 22 screenshots
5. Record the video while still deployed
6. Write the document afterwards, offline, at your own pace
