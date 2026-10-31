# IPP Hidden Portfolio Risk — beginner-friendly data validation starter
# Uses pandas and sqlite3; does not silently alter/normalize disclosed weights.
import pandas as pd
import sqlite3

DATA_FILE = "clean_data/standardized_portfolio_holdings.csv"
DATABASE_FILE = "database/hidden_portfolio_risk.db"

def load_data(file_name):
    """Load the standardised portfolio CSV into a Pandas DataFrame."""
    return pd.read_csv(file_name)

def validate_weights(data):
    """Summarise reported weight totals by scheme and source section."""
    section_totals = data.groupby(
        ["scheme_name", "source_section"]
    )["portfolio_weight_pct"].sum().reset_index()
    scheme_totals = data.groupby("scheme_name")[
        "portfolio_weight_pct"
    ].sum().reset_index(name="reported_total_weight_pct")
    return section_totals, scheme_totals

def save_to_sql(data, database_file):
    """Save the data into SQLite so it can be queried later."""
    connection = sqlite3.connect(database_file)
    data.to_sql("portfolio_holdings", connection, if_exists="replace", index=False)
    connection.close()

def main():
    data = load_data(DATA_FILE)
    section_totals, scheme_totals = validate_weights(data)
    print("Section totals:")
    print(section_totals.to_string(index=False))
    print("\nScheme totals (review before analysis):")
    print(scheme_totals.to_string(index=False))
    save_to_sql(data, DATABASE_FILE)
    print("\nData saved to SQLite. No weights were normalized or changed.")

if __name__ == "__main__":
    main()
