CATEGORIES = {
    "legal_threat": {
        "weight": 10, "auto_escalate": True,
        "patterns": [r"\b(lawyer|attorney|solicitor|advocate)s?\b", r"\blegal (action|notice|case|proceedings?)\b",
                     r"\b(sue|suing|lawsuit|court|consumer (forum|court|commission))\b", r"\bfile a case\b"],
        "keywords": [],
    },
    "safety_hazard": {
        "weight": 10, "auto_escalate": True,
        "patterns": [r"\b(caught|catch(es|ing)?) fire\b", r"\b(electric(al)? )?shock(ed)?\b", r"\bexplod\w*\b",
                     r"\b(injur\w+|hospital(i[sz]ed|s)?|burn(ed|t|s)?)\b", r"\bunsafe\b|\bdanger(ous)?\b|\boverheat\w*\b"],
        "keywords": [],
    },
    "fraud_security": {
        "weight": 9, "auto_escalate": True,
        "patterns": [r"\bfraud(ulent)?\b", r"\bscam(med)?\b", r"\bunauthori[sz]ed (charge|transaction|access|payment)s?\b",
                     r"\b(account|card) (was )?(hacked|compromised|stolen)\b", r"\bidentity theft\b", r"\bphishing\b"],
        "keywords": [],
    },
    "data_privacy": {
        "weight": 8, "auto_escalate": False,
        "patterns": [r"\bdata (breach|leak)\b", r"\bprivacy\b", r"\bgdpr\b", r"\bpersonal (data|information) (was )?(shared|leaked|exposed)\b",
                     r"\bshared my (data|details|information)\b"],
        "keywords": [],
    },
    "regulatory_pr": {
        "weight": 6, "auto_escalate": False,
        "patterns": [r"\b(regulator|ombudsman|rbi|trai|irdai|consumer protection)\b", r"\bsocial media\b|\btwitter\b|\bfacebook\b|\blinkedin\b",
                     r"\b(news|media|press|journalist)\b", r"\b(1[- ]star|one[- ]star)\b", r"\bpublic(ly)? (review|post|shame)\w*\b", r"\bgo viral\b"],
        "keywords": [],
    },
    "churn_threat": {
        "weight": 6, "auto_escalate": False,
        "patterns": [r"\b(cancel(l?ing)?|terminate|close) (my )?(account|subscription|membership|contract|service)\b",
                     r"\b(switch(ing)?|moving) to (a )?(competitor|another|someone else)\b", r"\bnever (buy|order|use)\b.*\bagain\b",
                     r"\blast (time|straw)\b", r"\btaking my business\b"],
        "keywords": [],
    },
    "billing_dispute": {
        "weight": 5, "auto_escalate": False,
        "patterns": [r"\bdouble[- ]?charged?\b|\bcharged twice\b", r"\boverchar\w+\b", r"\b(refund|chargeback)\b",
                     r"\bwrong(ly)? (bill|charge|amount)\w*\b", r"\bmoney (was )?(deducted|taken)\b", r"\bnot (received|got) (my )?refund\b"],
        "keywords": [],
    },
    "service_failure": {
        "weight": 4, "auto_escalate": False,
        "patterns": [r"\b(no|not any) (response|reply|callback|update)\b", r"\bnobody (called|replied|responded)\b",
                     r"\bstill (not )?(resolved|fixed|working|waiting)\b", r"\bunresolved\b", r"\bweeks?\b.*\b(waiting|pending|no)\b",
                     r"\b(defective|broken|damaged|faulty)\b", r"\bnever (arrived|delivered|received)\b"],
        "keywords": ["outage", "downtim"],
    },
    "abusive_anger": {
        "weight": 3, "auto_escalate": False,
        "patterns": [r"\b(worst|pathetic|useless|terrible|horrible|disgusting|ridiculous|unacceptable|incompetent)\b",
                     r"\bfed up\b|\bsick of\b|\bwaste of (time|money)\b", r"\bnever (again)\b"],
        "keywords": ["furiou", "outrag"],
    },
}

#phrases that reduce risk

DEESCALATION_PATTERNS = [r"\bthank(s| you)\b", r"\bresolved\b.*\b(now|already|thanks)\b", r"\bproblem (is )?solved\b",
                         r"\bno longer (an )?issue\b", r"\bjust (a )?(question|query|feedback)\b"]
DEESCALATION_POINTS = -3

#modifiers
URGENCY_PATTERNS = [r"\burgent(ly)?\b", r"\basap\b", r"\bimmediate(ly)?\b", r"\bright now\b", r"\btoday\b", r"\bemergency\b"]
URGENCY_POINTS = 2
REPEAT_TEXT_PATTERNS = [r"\b(third|fourth|fifth|3rd|4th|5th) time\b", r"\bagain and again\b", r"\bmultiple times\b",
                        r"\bseveral times\b", r"\bkeep(s)? (calling|asking|emailing)\b", r"\bnobody (has )?(helped|fixed)\b"]
REPEAT_TEXT_POINTS = 3
CAPS_RATIO_THRESHOLD = 0.35
CAPS_POINTS = 2
EXCLAMATION_THRESHOLD = 3 
EXCLAMATION_POINTS = 1
PRIOR_CONTACTS_THRESHOLD = 3
PRIOR_CONTACTS_POINTS = 3
TIER_POINTS = {"standard": 0, "silver": 1, "gold": 2, "vip": 3}

#dimnishing returns
EXTRA_HIT_FACTOR = 0.25

#categories after the first get this
SECONDARY_CATEGORY_FACTOR = 0.8

#Levles and escalation threshold

LEVELS = [("CRITICAL", 15), ("HIGH", 10), ("MEDIUM", 5), ("LOW", 0)]
ESCALATION_THRESHOLD = 10

#Routing/ Sla

SLA_HOURS = {"CRITICAL": 2, "HIGH": 8, "MEDIUM": 24, "LOW": 72}
QUEUES = {"standard": "STANDARD_SUPPORT", "senior": "SENIOR_SUPPORT"}

#statusWorflow
STATUSES = ["OPEN", "ESCALATED", "IN_PROGRESS", "RESOLVED", "CLOSED"]
TRANSITIONS = {
    "OPEN": {"ESCALATED", "IN_PROGRESS", "RESOLVED"},
    "ESCALATED": {"IN_PROGRESS", "RESOLVED"},
    "IN_PROGRESS": {"RESOLVED", "ESCALATED"},
    "RESOLVED": {"CLOSED", "IN_PROGRESS"},   # reopen allowed
    "CLOSED": set(),
}