import pandas as pd
import requests
import numpy as np
from io import StringIO
import time
import datetime
import matplotlib.pyplot as plt
import html5lib

from sqlalchemy import *
def connect_sql(database,echo):
    engine = create_engine("mysql+pymysql://gary:jack0705@localhost:3306/{}".format(database),echo=echo)
    return engine
engine = connect_sql('twse',False)


def y_m_generator(first_y, last_y):
    y_m = [(y,m) for y in range(first_y, last_y+1) for m in range(1, 13)]
    return y_m

# 生成網址
def url_generator(year, month):
    # url_0 = 'http://mops.twse.com.tw/nas/t21/sii/t21sc03_{}_{}_0.html'
    url = 'http://mops.twse.com.tw/nas/t21/sii/t21sc03_{}_{}.html'
    if year > 1900:
        year -= 1911
    url = url.format(year, month)
    return url

def monthly_sales(year, month):
    
    url = url_generator(year, month)
    
    # 偽瀏覽器
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) \
    AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
    
    # 取得該年月的資料
    r = requests.get(url, headers=headers)
    r.encoding = 'big5'
    
    # 轉換成 dataframe
    dfs = pd.read_html(StringIO(r.text), encoding='big-5')
    df = pd.concat([df for df in dfs if df.shape[1] <= 11 and df.shape[1] > 5])
    if 'levels' in dir(df.columns):
        df.columns = df.columns.get_level_values(1)
    else:
        df = df[list(range(0,10))]
        column_index = df.index[(df[0] == '公司代號')][0]
        df.columns = df.iloc[column_index]

    # 處理格式
    df['當月營收'] = pd.to_numeric(df['當月營收'], 'coerce')
    df = df[~df['當月營收'].isnull()]
    df = df[df['公司代號'] != '合計']
    if '備註' not in df.columns:
        df['備註'] = '-'
    df.rename(columns={'公司代號':'ID'            
                        ,'公司名稱':'NAME'
                        ,'當月營收':'Sales_This_Month'
                        ,'上月營收':'Sales_Last_Month'
                        ,'去年當月營收':'Sales_Last_Year'
                        ,'上月比較增減(%)':'MOM'      
                        ,'去年同月增減(%)':'YOY'    
                        ,'當月累計營收':'ACC_Sales_This_Year'
                        ,'去年累計營收':'ACC_Sales_Last_Year'
                        ,'前期比較增減(%)':'ACC_YOY'
                        ,'備註':'Remark'}, 
             inplace=True)
    df.drop_duplicates(subset='ID', keep='first', inplace=True)
    
    # 置換例外資料
    if (year,month)==(2013,1):
        df.replace(to_replace='不適用', value=np.NaN, inplace=True)
        
    # 偽停頓
    time.sleep(5)

    return df

def sales_aggregate(Id):
    y_m = y_m_generator(2010, 2018)
    # y_m_str = [str(y)+'0'+str(m) if m<10 else str(y)+str(m) for y,m in y_m_generator(2013, 2018)]
    dfs = []
    for y,m in y_m:
        p = str(y)+'0'+str(m) if m<10 else str(y)+str(m)
        (mapping_y, mapping_m) = (y, m+1) if m!=12 else (y+1, 1)
        df = pd.read_sql_query('select * from SII_REV_{} where ID = "{}"'.format(p, Id), con=engine)
        df['Y_M'] = p
        df['Sales_Public_Date'] = datetime.datetime(mapping_y,mapping_m,7,0,0,0)
        cols = df.columns.tolist()
        cols = cols[-2:] + cols[:-2]
        df = df[cols]
        dfs.append(df)
    df = pd.concat(dfs)
    return df


















def raw_incm(year, season):
    url = 'https://mops.twse.com.tw/mops/web/t163sb04'
    r = requests.post(url, {
            'encodeURIComponent':1,
            'step':1,
            'firstin':1,
            'off':1,
            'TYPEK':'sii',
            'year':year,
            'season':season,
        })
    r.encoding = 'utf8'
    return r.text

def unify_incm(x):
    dfs = x.copy()
    dfs[0]['Gross_Profit'] = dfs[0]['利息淨收益'] + dfs[0]['利息以外淨損益']
    dfs[0].rename(columns={'繼續營業單位稅前淨利（淨損）':'Operating_Income',
                              '本期稅後淨利（淨損）':'Net_Income'}, inplace=True)
    dfs[0]['Pre_Tax_Income'] = dfs[0]['Operating_Income']

    dfs[1].rename(columns={'收益':'Gross_Profit',
                              '營業利益':'Operating_Income',
                              '稅前淨利（淨損）':'Pre_Tax_Income',
                              '本期淨利（淨損）':'Net_Income'}, inplace=True)

    dfs[2].rename(columns={'營業收入':'Gross_Profit',
                              '營業利益（損失）':'Operating_Income',
                              '稅前淨利（淨損）':'Pre_Tax_Income',
                              '本期淨利（淨損）':'Net_Income'}, inplace=True)

    dfs[3].rename(columns={'淨收益':'Gross_Profit',
                              '繼續營業單位稅前損益':'Operating_Income',
                              '本期稅後淨利（淨損）':'Net_Income'}, inplace=True)
    dfs[3]['Pre_Tax_Income'] = dfs[3]['Operating_Income']

    dfs[4].rename(columns={'營業收入':'Gross_Profit',
                              '營業利益（損失）':'Operating_Income',
                              '繼續營業單位稅前純益（純損）':'Pre_Tax_Income',
                              '本期淨利（淨損）':'Net_Income'}, inplace=True)
    for i in dfs:
        i.rename(columns={'公司代號':'Id','公司名稱':'Name','基本每股盈餘（元）':'EPS'}, inplace=True)
        
    dfs = [i[['Id', 'Name', 'Gross_Profit', 'Operating_Income', 'Pre_Tax_Income', 'Net_Income', 'EPS']] for i in dfs]
    
    return dfs

def get_incm(year, season):

    if year >= 1000:
        year -= 1911
        
    dfs = pd.read_html(raw_incm(year, season))
    
    dfs = [i for i in dfs if i.shape[1] > 20]
    
    # 將不同欄位名統一
    df_all = pd.concat(unify_incm(dfs), ignore_index=True)
    
    # 偽停頓
    time.sleep(1)
    
    return df_all