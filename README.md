📊 Financial Transparency Dashboard
Overview
This project is a financial data dashboard designed to deliver transparent and distortion-free financial insights to investors.
The system builds a structured data pipeline from raw OpenDART API responses to normalized financial metrics and interactive visualizations.


🎯 Objectives
Ensure traceability from raw financial statements to calculated KPIs
Compare multiple companies across key financial dimensions
Provide intuitive visualization without sacrificing numerical accuracy
Demonstrate full-stack data engineering capability


🏗 System Architecture
OpenDART API
      ↓
Raw JSON Storage
      ↓
Data Normalization (pandas)
      ↓
Financial Metric Calculation
      ↓
SQLAlchemy ORM → SQLite
      ↓
Streamlit Dashboard


📌 Key Features
Multi-company comparison (up to 3 companies)
Industry average benchmarking
KPI summary cards with YoY growth indicators
Growth, Profitability, Stability, and Cash Flow analysis tabs
Custom financial metric computation (ROE, ROA, FCF, Debt Ratio, CAGR)
Data validation and anomaly detection


📊 Core Financial Metrics
1. Growth
Revenue Growth, Operating Income Growth, 3-Year CAGR

2. Profitability
ROE, ROA, Operating Margin, Net Margin

3. Stability
Debt Ratio, Current Ratio, Interest Coverage Ratio

4. Cash Flow
Operating Cash Flow, Free Cash Flow, Net Cash Change


⚙ Tech Stack
Python
pandas / numpy
SQLAlchemy
Streamlit
Plotly
OpenDART API


▶ How to Run
pip install -r requirements.txt
uvicorn backend.main:app --reload


🚀 Future Improvements
Automated periodic updates
Financial health scoring model
Exportable PDF investment report
Docker deployment