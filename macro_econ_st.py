import pandas as pd
import altair as alt
import requests
import numpy as np
import streamlit as st 
import pandas_datareader as pdr

def get_real_gdp(BEA_file):
    GDP_Q = (BEA_file.parse(sheet_name = "T10101-Q",skiprows=7)
    .drop(columns=['Line'])
    .rename(columns = {'Unnamed: 1': 'Account' , 
                    'Unnamed: 2' : 'Code'})
    .melt(id_vars = ['Account' , 'Code'],
        var_name = 'date',
        value_name = 'percent_change')
    .assign(percent_change = lambda df: pd.to_numeric(df['percent_change'], errors = 'coerce'), 
            date = lambda df: pd.to_datetime(df['date']),
        date_yr = lambda df: df['date'].dt.year,
        date_qtr = lambda df: df['date'].dt.quarter,
        date_month = lambda df: df['date'].dt.month))

    GDP_Q_Pct_Chng = GDP_Q.query('Account.str.strip() == "Gross domestic product"').reset_index()
    return GDP_Q_Pct_Chng

def create_boxplot(df_GDP):
    box_base = alt.Chart(df_GDP).mark_boxplot(size=50).encode(
            alt.Y("percent_change:Q").scale(zero= False, domain=[-40,40]).title('% Change'),
            alt.X("date_qtr:N").title('Fiscal Quarter').axis(labelAngle=0),
            tooltip=[alt.Tooltip("percent_change:Q", format = ",.2f")]).properties(width=400, height=400)
        

    invisible_bar = alt.Chart(df_GDP).transform_aggregate(
        Min = "min(percent_change)",
        Max= "max(percent_change)",
        Mean= "mean(percent_change)",
        Median ="median(percent_change)",
        Q3 = "q3(percent_change)",
        Q1 = "q1(percent_change)",
        Count = "count()",
        groupby=['date_qtr']
        ).transform_calculate(
            IQR="datum.Q3 - datum.Q1"
        ).mark_bar(opacity=0).encode(x = "date_qtr:N", y="Q1:Q", y2="Q3",
        tooltip=
            alt.Tooltip(['Count:Q','Max:Q', 'Q3:Q', 'Mean:Q', 'Median:Q', 'IQR:Q', 'Q1:Q', 'Min:Q'], format=".2f")
        )
    return box_base + invisible_bar

def create_histogram(df_GDP, option, start_date, end_date, step_size):
    if option == 'Expansion':
        period_flag = 0
        df_GDP = df_GDP.query(f'USREC == {period_flag} and ((date >= "{start_date}") and (date <= "{end_date}"))')
    elif option == 'Recession':
        period_flag = 1
        df_GDP = df_GDP.query(f'USREC == {period_flag} and ((date >= "{start_date}") and (date <= "{end_date}"))')
    else:
        df_GDP = df_GDP.query(f'((date >= "{start_date}") and (date <= "{end_date}"))')
    print(df_GDP)
    select = alt.selection_point("Point_Selection", encodings=['x'])

    bars = alt.Chart(df_GDP).mark_bar().encode(
        alt.X("percent_change:Q").bin(maxbins=20,step=step_size).scale(domain=[-40,40]).title('Percent Change in GDP (bins)'),
        alt.Y('count()'),
        alt.Color("percent_change:Q").bin(maxbins=20,step=step_size).scale(scheme='pinkyellowgreen'),
    ).add_params(select).properties(width=500,height=500)

    bars_selection = alt.Chart(df_GDP).mark_bar().encode(
        alt.X("percent_change:Q").bin(maxbins=20,step=step_size).scale(domain=[-40,40]).title('Percent Change in GDP (bins)'),
        alt.Y('count()'),
        alt.Color("percent_change:Q").bin(maxbins=20,step=step_size).scale(scheme='pinkyellowgreen'),
    ).transform_filter(select)

    ranked_text = alt.Chart(df_GDP).mark_text(align='right').encode(
        y=alt.Y('row_number:O', axis=None, sort=alt.EncodingSortField('percent_change', order="descending"))
    ).transform_filter(
        select
    ).transform_window(
        row_number='row_number()'
    ).transform_filter(
        'datum.row_number < 25'
    )
    labels = alt.Chart(df_GDP).mark_text(
        align='center',
        baseline='middle',
        dy=-5  
    ).encode(
        x=alt.X("percent_change:Q", bin=alt.Bin(step=3)),
        y='count():Q',
    text='count():Q'
    )   
    
    date = ranked_text.encode(text='date:T').properties(title=alt.TitleParams(text='Date', align='right'))
    quarter = ranked_text.encode(text='date_qtr:N').properties(title=alt.TitleParams(text='Quarter', align='right'))
    pchange = ranked_text.encode(text='percent_change:Q').properties(title=alt.TitleParams(text='% Change', align='right'))
    text = alt.vconcat(date, quarter, pchange) 

    histogram_data_table = alt.vconcat(
    bars+bars_selection+labels,
        text
    ).resolve_legend(
        color="independent"
    ).configure_view(strokeWidth=0)

    return histogram_data_table
def get_recession_indicator(df): 
    return pdr.get_data_fred('USREC',start = min(df.date)).reset_index().rename(columns={'DATE' : 'date'})

url = 'https://apps.bea.gov/national/Release/XLS/Survey/Section1All_xls.xlsx'
#BEA_file = pd.ExcelFile(url)
df_GDP = get_real_gdp(pd.ExcelFile(url))
rec_ind_df = get_recession_indicator(df_GDP)
merge_GDP_ind_df = df_GDP.merge(rec_ind_df, on='date', how='left')
with st.container():
    st.altair_chart(create_boxplot(df_GDP), use_container_width=True)
    

with st.container():
    unique_dates = sorted(merge_GDP_ind_df['date'].unique())
    start_date, end_date = st.select_slider(
    "Select a date range",
    options=unique_dates,
    value=(min(unique_dates), max(unique_dates))
)
    option = st.selectbox("Filter data on periods", ("All", "Expansion", "Recession"), index = 0)
    if "data" not in st.session_state:
        st.session_state.data = merge_GDP_ind_df

    
    st.altair_chart(create_histogram(merge_GDP_ind_df, option, start_date, end_date, 3),key="alt_chart", on_select="rerun", use_container_width=True)

