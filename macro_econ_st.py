import pandas as pd
import altair as alt
import requests
import numpy as np
import streamlit as st 
import pandas_datareader as pdr
def create_chloropleth(df, counties_url):
    counties = alt.topo_feature(counties_url,'counties')
    selection = alt.selection_point(fields=['Value'])
    color = alt.condition(selection,
                alt.Color('Value:Q',
                scale=alt.Scale(scheme='viridis'),
                legend=alt.Legend(title='Rate', gradientLength=300)),
                alt.value('lightgray'))
    base = alt.Chart(counties).mark_geoshape(stroke='black',
            strokeWidth=1).encode(
        color=color,#tooltip="Value:Q"
        tooltip=[
            alt.Tooltip("County:O", title="Name"),
            alt.Tooltip("Lowest_Unemployment:O", title="Lowest UnRate"),
            alt.Tooltip("Highest_Unemployment:O", title="Highest UnRate"),
            alt.Tooltip("Lowest_Unemployment_Date:O", title="Lowest UnRate Date"),
            alt.Tooltip("Highest_Unemployment_Date:O", title="Highest UnRate Date"),
            alt.Tooltip("Value:O", title="Rate")] #Highest_Unemployment	Lowest_Unemploymen
    ).transform_lookup(
        lookup='id',
        from_=alt.LookupData(df, 'Lookup_id', ['Value', 'County','Highest_Unemployment'	,'Lowest_Unemployment','Highest_Unemployment_Date','Lowest_Unemployment_Date'])
    ).project(
        type='albersUsa'
    ).properties(
        width=900,
        height=700
    ).add_params(selection)

    return base
def flatten_data_chloro(chloropleth_df):
    min_max_dates_df = chloropleth_df.groupby(['County', 'State'], as_index=False).agg(
    Highest_Unemployment=('Value', 'max'),
    Lowest_Unemployment=('Value', 'min'))

    highest_dates_df = chloropleth_df.loc[chloropleth_df.groupby(['County', 'State'])['Value'].idxmax(), ['County', 'State', 'DATE']]
    highest_dates_df.rename(columns={'DATE': 'Highest_Unemployment_Date'}, inplace=True)

    lowest_dates_df = chloropleth_df.loc[chloropleth_df.groupby(['County', 'State'])['Value'].idxmin(), ['County', 'State', 'DATE']]
    lowest_dates_df.rename(columns={'DATE': 'Lowest_Unemployment_Date'}, inplace=True)

    min_max_with_dates_df = pd.merge(min_max_dates_df, highest_dates_df, on=['County', 'State'], how='left')
    min_max_with_dates_df = pd.merge(min_max_with_dates_df, lowest_dates_df, on=['County', 'State'], how='left')

    filtered_df = chloropleth_df[chloropleth_df['DATE'] == "2024-07-01"]

    return pd.merge(filtered_df, min_max_with_dates_df, on=['County', 'State'], how='left')

def get_county_dataset(file_path):
    sheet_names = [f"Monthly_{i}" for i in range(1, 14)]
    merged_df=pd.DataFrame()
    for sheet in sheet_names:
        current_df = pd.read_excel(file_path, sheet_name=sheet)
        
        if merged_df.empty:
            merged_df = current_df
        else:
            merged_df = merged_df.merge(current_df, on='DATE', how='left')
    return pd.melt(merged_df, id_vars=['DATE'], var_name='Series_Type', value_name='Value')

def match_state_codes(df_names,state_codes):
    lookup_ids = []

    for index, row in df_names.iterrows():
        county = row['County']
        state = row['State']

        match = state_codes[(state_codes['COUNTYNAME'].str.upper() == county.upper()) & (state_codes['STATE'] == state)]
        
        if not match.empty:
            lookup_id = match['STATEFP'].astype(int).astype(str).values[0] + match['COUNTYFP'].values[0]
            lookup_ids.append(lookup_id)
        else:
            lookup_ids.append('NA')

    df_names['Lookup_id'] = lookup_ids
    return df_names

def split_description(description):
    state = description.split(',')[-1].strip()
    county_or_area = description.split(' in ')[-1].split(',')[0].strip()
    
    return county_or_area, state

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
    text = alt.hconcat(date, quarter, pchange) 

    histogram_data_table = alt.hconcat(
    bars+bars_selection+labels,
        text
    ).resolve_legend(
        color="independent"
    ).configure_view(strokeWidth=0)

    return histogram_data_table
def get_recession_indicator(df): 
    return pdr.get_data_fred('USREC',start = min(df.date)).reset_index().rename(columns={'DATE' : 'date'})

GDP_url = 'https://apps.bea.gov/national/Release/XLS/Survey/Section1All_xls.xlsx'
url_2 = "https://view.officeapps.live.com/op/view.aspx?src=https%3A%2F%2Fraw.githubusercontent.com%2Fwalkawalker%2Fstreamlit_macro%2Frefs%2Fheads%2Fmain%2FCounties_UnRate.xls&wdOrigin=BROWSELINK"
match_keys_url = "https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt"
names_url = "https://raw.githubusercontent.com/walkawalker/streamlit_macro/refs/heads/main/Counties_UnRate_Names.csv"
missing_url = "https://raw.githubusercontent.com/walkawalker/streamlit_macro/refs/heads/main/Counties_UnRate_Missing_edited.csv"
counties_url = 'https://raw.githubusercontent.com/walkawalker/streamlit_macro/refs/heads/main/counties.json'
#BEA_file = pd.ExcelFile(url)
df_GDP = get_real_gdp(pd.ExcelFile(GDP_url))
rec_ind_df = get_recession_indicator(df_GDP)
merge_GDP_ind_df = df_GDP.merge(rec_ind_df, on='date', how='left')

df_state_codes = pd.read_csv(match_keys_url, delimiter='|')
df_state_codes['COUNTYFP']=df_state_codes['COUNTYFP'].astype(str).str.zfill(3)
df_names = pd.read_csv(names_url)
df_names.drop(columns = ['Unnamed: 0'],inplace = True)
df_names[['County','State']] = df_names['Series_Name'].apply(split_description).apply(pd.Series)
df_missing = pd.read_csv(missing_url)
df_missing.drop(columns = ['Unnamed: 0'],inplace = True)

match_df = match_state_codes(df_names, df_state_codes)
resultant_df = pd.concat([match_df,df_missing])
df_county_long = get_county_dataset(url_2)
chloropleth_df = df_county_long.merge(resultant_df, on='Series_Type', how='left')

with st.container():
    st.altair_chart(create_boxplot(df_GDP), use_container_width=True)
    
'''
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
'''
with st.container():
    st.altair_chart(create_chloropleth(flatten_data_chloro(chloropleth_df),counties_url), use_container_width=True)