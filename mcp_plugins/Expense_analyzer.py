# this program handles (pdf / csv ) file turns into categorizes transactions with  static keyword rules, and prints a monthly spend summary + graph option.

# import nessary modules
import re
from pathlib import Path
import pdfplumber
import pandas as pd
import plotext as plt2
from rich.console import Console
from rich.panel import Panel

# setting up the console
console = Console()

# defining rules for payment data / catogrizing data about the payment
CATEGORY_RULES = {
    "Food": ["zomato", "swiggy", "restaurant", "food"],
    "Travel": ["uber", "ola", "irctc", "redbus", "metro", "petrol", "fuel"],
    "Shopping": ["amazon", "flipkart", "myntra"],
    "Bills": ["recharge", "electricity", "broadband", "airtel", "jio"],
}

# Defining rules 
PEOPLE_RULE = {
    "Dad" :["dad@", "father@"] # add details of your known / beloved one
}


# this function converts a PDF or CSV statement into a normalized DataFrame
def load_statement(path: str) -> pd.DataFrame:
    """Load a bank/GPay statement (.csv or .pdf) into a normalized
    DataFrame with columns: date, description, amount (signed —
    negative = spend, positive = received)."""

    # defining the path
    path = Path(path)

    # this condition checks if the path is PDF or CSV
    if path.suffix.lower() == ".csv":
        return _load_csv(path)
    elif path.suffix.lower() == ".pdf":
        return _load_pdf(path)
    raise ValueError (f"[Fox]: Unsupported file type - {path.suffix}")

# this function loads and normalizes transaction data from a CSV file
def _load_csv(path: Path):
    raw = pd.read_csv(path)

    cols = {c.lower(): c for c in raw.columns}

    # this helper finds the first matching column name from the CSV
    def find(*candidates):
        for cand in candidates:
            for lower, original in cols.items():
                if cand in  lower:
                    return original
        return None

    # creatung variable to fetch details from CSV
    date_col = find("date") # this fetch date
    desc_col = find("narration", "decription", "particukars", "remark") # this fetch description
    amt_col = find("amount") # this fetch amount....

    if not all([date_col, desc_col, amt_col]):
        raise ValueError(
            f"[Fox]: Couldn't find date/description/amount columns in {list(raw.columns)}. "
            "Rename them or extend the `find()` candidates."
        )

    df = pd.DataFrame({
        "date": pd.to_datetime(raw[date_col], errors = "coerce", dayfirst = True),
        "description" : raw[desc_col].astype(str),
        "amount": pd.to_numeric(raw[amt_col], errors="coerce")
    })
    return df.dropna(subset = ["date", "amount"])

# this function extracts and normalizes transaction data from a PDF file
def _load_pdf(path: Path):
    rows = []

    line_pattern = re.compile(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.*?)\s+([-+]?\d[\d,]*\.?\d*)\s*$")

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                m = line_pattern.match(line.strip())
                if not m:
                    continue
                date_str, desc, amt_str = m.groups()
                rows.append({
                    "date": date_str,
                    "description": desc.strip(),
                    "amount": float(amt_str.replace(",",""))
                })

    if not rows:
        raise ValueError(
            "[Fox]: No transaction lines matched in the PDF. "
            "Send a sample so I can fix the line pattern."
        )

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors = "coerce", dayfirst = True)
    return df.dropna(subset = ["date"])

# this function assigns a category by matching description keywords
def categorize(desc: str) -> str:
    desc_1 = desc.lower()
    for label, keywords in PEOPLE_RULE.items():
        if any(k in desc_1 for k in keywords):
            return label
    for category, keywords in CATEGORY_RULES.items():
        if any(k in desc_1 for k in keywords):
            return category
    return "Other"

# this function builds the current-month spending summary
def build_summary(df: pd.DataFrame):
    df = df.copy()
    df["category"] = df["description"].apply(categorize)
    df["month"] = df["date"].dt.to_period("M")

    months = sorted(df["month"].unique())
    if not months:
        return None
    current_month = months[-1]
    prev_month = months[-2] if len(months) >1 else None

    cur =  df[df["month"] == current_month]
    by_category = cur.groupby("category")["amount"].sum().sort_index()

    total_spend = -cur[cur["amount"] < 0]["amount"].sum() 

    prev_spend = None
    if prev_month is not None:
        prev = df[df["month"] == prev_month]
        prev_spend = -prev[prev["amount"] < 0] ["amount"].sum()

    return {
        "month": current_month,
        "by_category": by_category,
        "total_spend": total_spend,
        "prev_spend": prev_spend
    }

# this function formats and prints the spending summary
def print_summary(summary: dict):
    if summary is None:
        console.print("[Fox]: No transactions found.....")
        return

    lines = [f"This Month Track ({summary['month']})\n"]
    for category, amount in summary["by_category"].items():
        sign = "+" if amount >= 0 else "-"
        lines.append(f"{category:<10}>: {sign}₹{abs(amount):.0f}")
         
    lines.append(f"\nTotal spend = ₹{summary['total_spend']:.0f}")

    if summary["prev_spend"] not in (None, 0):
        diff = summary ["total_spend"] - summary["prev_spend"]
        pct = (diff/summary["prev_spend"]) * 100
        direction = "extra" if diff >= 0 else "less"
        lines.append(
            f"that's {pct:+.0f}% which is {direction} \u20b9{abs(diff):.0f}"
            " compared to previous month"
        )
    console.print(Panel.fit("\n".join(lines), title="[Fox]: Expense Summary"))

# this function displays a bar chart of spending by category
def plot_category_bar(summary: dict):
    by_category = summary["by_category"]
    plt2.bar(by_category.index.tolist(), by_category.values.tolist())
    plt2.title(f"Spend by Category — {summary['month']}")
    plt2.xlabel("Category")
    plt2.ylabel("Amount")
    plt2.show()

# this function runs the interactive expense analyzer flow
def run_expense_analyzer():
    """Entry point wired into the Finance Bot menu"""
    path = input("[Fox]: Path to statement (.csv or .pdf): ").strip()
    try:
        df = load_statement(path)
    except Exception as e:
        console.print(f"[Fox]: {e}")
        return

    summary = build_summary(df)
    print_summary(summary)

    if summary is None:
        return

    console.print(Panel.fit(
        "[bold blue]1[/bold blue]. Bar graph (spend by category)\n"
        "[bold blue]0[/bold blue]. Skip",
        title="[Fox]: Visualization Options"
    ))

    choice = input("[Fox]: Choose: ").strip()
    if choice == "1":
        plot_category_bar(summary)

if __name__ == "__main__":
    run_expense_analyzer()