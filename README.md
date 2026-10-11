# Customer Complaint Escalation Assistant

Reads customer complaints, scores how risky they are, and automatically sends
high-risk ones to a senior support queue.

```
Complaint -> Risk Analysis -> Escalation Flag -> Senior Queue -> Status Tracking
```

## How it works

1. **Detect**: regex patterns find risky phrases (e.g. "lawyer", "caught fire", "charged twice").
2. **Score**: each topic adds points, with extras for warning signs.
3. **Flag**: score of 10 or more, or any legal, safety or fraud issue, means escalate.
4. **Route**: flagged tickets go to `SENIOR_SUPPORT` with a reply deadline; others go to `STANDARD_SUPPORT`.
5. **Track**: every status change is saved in a history log.

**Example:** "I will contact my lawyer if this isn't fixed today!"
legal threat (+10) + urgency (+2) = **12, HIGH, escalated** to the senior queue.

## Risk scoring

| Category | Points | Always escalate |
|---|:-:|:-:|
| Legal threat | 10 | Yes |
| Safety hazard | 10 | Yes |
| Fraud / security | 9 | Yes |
| Data privacy | 8 | |
| Regulator / public image | 6 | |
| Threat to leave | 6 | |
| Billing dispute | 5 | |
| Service failure | 4 | |
| Anger | 3 | |

**Extra points:** urgent words +2, repeat contact +3, ALL CAPS +2, "!!!" +1,
3+ earlier contacts +3, Silver/Gold/VIP customer +1/+2/+3.
**Less points:** "thank you" / "resolved" -3 (never for legal, safety, fraud).

| Score | Level | Reply deadline |
|---|---|---|
| 0-4.9 | LOW | 72 h |
| 5-9.9 | MEDIUM | 24 h |
| 10-14.9 | HIGH | 8 h |
| 15+ | CRITICAL | 2 h |

Every result lists its reasons, so agents can see why a ticket was flagged.

## Ticket status

```
OPEN -> ESCALATED -> IN_PROGRESS -> RESOLVED -> CLOSED
```

Invalid jumps are rejected, resolved tickets can be re-opened, and closed
tickets are final.

## Run it

Needs Python 3.9+. Install the app's packages once: `pip install -r requirements.txt`
(NLTK is optional but recommended).

```bash
streamlit run app.py                      # open the web app (recommended)
python main.py demo                       # run on 28 sample complaints
python main.py analyze "your text here"   # score one complaint
python -m unittest discover -s tests -v   # run 26 tests
```

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit web app |
| `escalation/config.py` | categories, words, points, rules |
| `escalation/analyzer.py` | detection and scoring |
| `escalation/db.py` | SQLite CRM tickets and history |
| `escalation/workflow.py` | ticket creation, routing, status |
| `data/complaints.csv` | sample dataset |
| `tests/test_escalation.py` | test cases |

## Limitations

Rule-based, so it can't understand negation ("I will *not* sue") or sarcasm,
and works in English only. Future idea: add sentiment analysis (NLTK VADER).