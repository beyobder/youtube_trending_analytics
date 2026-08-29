import os
import glob
import pandas as pd
from sqlalchemy import create_engine

# 1. Database Connection Parameters (Update with your pgAdmin credentials)
DB_USER = "postgres"
DB_PASS = "your_password"  # Replace with your PostgreSQL password
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "youtube_analytics"  # Ensure this database is created in pgAdmin

# 2. Create SQLAlchemy Engine
engine = create_engine(
    f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# 3. Path to your data folder containing the CSV files
data_folder = "./data/youtube_trending_analytics"

# 4. Iterate over CSV files and write to PostgreSQL
for file_path in glob.glob(os.path.join(data_folder, "*videos.csv")):
    file_name = os.path.basename(file_path)
    country_code = file_name[:2].lower()  # e.g., 'ca' from 'CAvideos.csv'
    table_name = f"trending_{country_code}"

    print(f"Loading {file_name} into table '{table_name}'...")

    # Read CSV with encoding standard for YouTube dataset
    df = pd.read_csv(file_path, encoding="latin1")

    # Upload to PostgreSQL table
    df.to_sql(
        table_name, engine, if_exists="replace", index=False, method="multi"
    )

print("All CSV files have been converted and uploaded to PostgreSQL!")