from pathlib import Path

MASTER_ROOT = Path(__file__).resolve().parent.parent

SCHEDULE_BOT_ROOT = MASTER_ROOT / "Schedule_Bot"
DATA_ROOT = SCHEDULE_BOT_ROOT / "Data"
SCHEDULE_CSV = DATA_ROOT / "schedule.csv"