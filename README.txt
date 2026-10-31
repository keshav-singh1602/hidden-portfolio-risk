IPP HIDDEN PORTFOLIO RISK — DATA PACKAGE v2

Date: 29 October 2026
Scope: September 2026 holdings from five selected mutual fund schemes.

FOLDERS
- raw_source_files/: supplied original CSV exports; do not edit these.
- clean_data/: standardised holdings and metadata.
- sector_classification/: working mapping, verification register, and notes.
- validation/: section/portfolio weight checks and manual test evidence.
- python_code/: beginner-oriented Python scripts.
- tests/: small, manually checked unit tests.
- outputs/: analysis tables, charts, scenario outputs, and preliminary findings.
- database/: SQLite database.

RUN THE ANALYSIS
From this package folder:
    python python_code/03_final_analysis.py

RUN THE TESTS
    python -m unittest discover -s tests -v

IMPORTANT LIMITATIONS
1. Portfolio CSVs were supplied from RupeeVest. Cross-check original AMC monthly disclosures before final submission.
2. No issuer-to-sector row is marked officially verified yet. The accessible NSE Indices page explains the taxonomy and methodology, but the complete company-level mapping still needs an official issuer-level source. Name-based assignments are provisional.
3. ICICI Prudential Large Cap Fund reported section weights sum to 102.00%, including a 1.96% Infosys futures line. Excluding it gives 100.04%, but the line has not been removed or normalised. Reconcile to the official AMC portfolio and treatment of derivative exposure.
4. UTI's supplied export shows AUM as a dash. No AUM was invented.
5. Duplicate-looking debt instruments and treasury bills are retained because names alone do not prove they are duplicates.
6. Sector exposures and sector stress tests are provisional. Do not present them as final results until the mapping has been verified.
7. The Diversification Gap is a relative rank indicator within these five schemes, not a universal risk measure. Scheme mandates differ, including HDFC Balanced Advantage (hybrid) and UTI Nifty 50 Index (index fund).
8. Stress tests are hypothetical direct arithmetic sensitivities, not forecasts or investment recommendations.

OFFICIAL CLASSIFICATION REFERENCE
NSE Indices Industry Classification:
https://www.nseindia.com/static/products-services/industry-classification
NSE Indices Resources:
https://www.niftyindices.com/resources/industry-classification


VERSION 3 ADDITIONS
- outputs/BUSINESS_FINDINGS_AND_RECOMMENDATIONS.txt
- outputs/Business_Findings_and_Recommendations.docx
- The current sector mapping is treated as a working assumption only; it is not described as fully officially verified.


FRONTEND DASHBOARD
Install dependencies: python -m pip install -r requirements.txt
Run dashboard: python -m streamlit run app.py
See FRONTEND_QUICK_START.txt for steps and limitations.
