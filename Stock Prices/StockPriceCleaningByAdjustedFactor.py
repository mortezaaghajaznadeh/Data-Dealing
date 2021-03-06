#%%
import pandas as pd
import numpy as np
import re
import statsmodels.api as sm
import finance_byu.rolling as rolling
import requests
import pandas as pd
from bs4 import BeautifulSoup
import math


def convert_ar_characters(input_str):

    mapping = {
        "ك": "ک",
        "گ": "گ",
        "دِ": "د",
        "بِ": "ب",
        "زِ": "ز",
        "ذِ": "ذ",
        "شِ": "ش",
        "سِ": "س",
        "ى": "ی",
        "ي": "ی",
    }
    return _multiple_replace(mapping, input_str)


def _multiple_replace(mapping, text):
    pattern = "|".join(map(re.escape, mapping.keys()))
    return re.sub(pattern, lambda m: mapping[m.group()], str(text))


def vv(row):
    X = row.split("-")
    return int(X[0] + X[1] + X[2])


def vv2(row):
    X = row.split("/")
    return int(X[0] + X[1] + X[2])


def addDash(row):
    row = str(row)
    X = [1, 1, 1]
    X[0] = row[0:4]
    X[1] = row[4:6]
    X[2] = row[6:8]
    return X[0] + "-" + X[1] + "-" + X[2]


def removeSlash(row):
    X = row.split("/")
    if len(X[1]) < 2:
        X[1] = "0" + X[1]
    if len(X[2]) < 2:
        X[2] = "0" + X[2]
    return int(X[0] + X[1] + X[2])


def removeSlash2(row):
    X = row.split("/")
    if len(X[1]) < 2:
        X[1] = "0" + X[1]
    if len(X[0]) < 2:
        X[0] = "0" + X[0]

    return int(X[2] + X[0] + X[1])


def removeDash(row):
    X = row.split("-")
    if len(X[1]) < 2:
        X[1] = "0" + X[1]
    if len(X[2]) < 2:
        X[2] = "0" + X[2]
    return int(X[0] + X[1] + X[2])


path = r"G:\Economics\Finance(Prof.Heidari-Aghajanzadeh)\Data\Capital Rise\\"
#%%
def group_id():
    r = requests.get(
        "http://www.tsetmc.com/Loader.aspx?ParTree=111C1213"
    )  # This URL contains all sector groups.
    soup = BeautifulSoup(r.text, "html.parser")
    header = soup.find_all("table")[0].find("tr")
    list_header = []
    for items in header:
        try:
            list_header.append(items.get_text())
        except:
            continue

    # for getting the data
    HTML_data = soup.find_all("table")[0].find_all("tr")[1:]
    data = []
    for element in HTML_data:
        sub_data = []
        for sub_element in element:
            try:
                sub_data.append(sub_element.get_text())
            except:
                continue
        data.append(sub_data)
    df = pd.DataFrame(data=data, columns=list_header).rename(
        columns={"گروه های صنعت": "group_name", "کد گروه های صنعت": "group_id"}
    )
    return df


groupnameid = group_id()
# %%
pdf = pd.read_parquet(path + "Stocks_Prices_1400-04-27.parquet")


mapdict = dict(zip(groupnameid.group_name, groupnameid.group_id))
pdf["group_id"] = pdf.group_name.map(mapdict)


pdf.loc[pdf.name.str[-1] == " ", "name"] = pdf.loc[pdf.name.str[-1] == " "].name.str[
    :-1
]
pdf.loc[pdf.name.str[0] == " ", "name"] = pdf.loc[pdf.name.str[0] == " "].name.str[1:]
pdf["name"] = pdf["name"].apply(lambda x: convert_ar_characters(x))
pdf.jalaliDate = pdf.jalaliDate.apply(vv)
pdf = pdf.sort_values(by=["name", "date"])
pdf = pdf[
    ~((pdf.title.str.startswith("ح")) & (pdf.name.str.endswith("ح")))
]  # delete right offers
pdf = pdf[~(pdf.name.str.endswith("پذيره"))]  # delete subscribed symbols
pdf = pdf[~(pdf.group_name == "صندوق سرمايه گذاري قابل معامله")]  # delete ETFs

col = "name"
pdf[col] = pdf[col].apply(lambda x: convert_ar_characters(x))

#%%
symbolGroup = pdf[["name", "group_name", "group_id"]].drop_duplicates(
    subset=["name", "group_name", "group_id"]
)
path2 = r"G:\Economics\Finance(Prof.Heidari-Aghajanzadeh)\Data\\"
symbolGroup.to_excel(path2 + "SymbolGroup.xlsx", index=False)


#%%

## get Adjusted factor for adjusted Price

adData = pd.read_csv(path + "DataAdjustedEvent.csv")
adData = (
    adData.rename(
        columns={"قبل از تعدیل": "Before", "تعدیل شده": "After", "تاریخ": "jalaliDate"}
    )
    .sort_values(by=["stock_id", "jalaliDate"])
    .drop_duplicates(subset=["stock_id", "jalaliDate"], keep="last")
)
gg = adData.groupby("stock_id")


def clean(g):
    g.loc[g.After == 1, "After"] = np.nan
    g.loc[g.Before == 1, "Before"] = np.nan
    g["After"] = g["After"].fillna(method="bfill")
    g["Before"] = g["Before"].fillna(method="ffill")
    return g


adData = gg.apply(clean)
adData["AdjustFactor"] = adData.After / adData.Before
gg = adData.groupby("stock_id")
adData["AdjustFactor"] = gg.AdjustFactor.cumprod()

i = "stock_id"
pdf[i] = pdf[i].astype(str)
adData[i] = adData[i].astype(str)
i = "jalaliDate"
pdf[i] = pdf[i].astype(int)
adData[i] = adData[i].astype(int)

pdf = pdf.merge(
    adData[["jalaliDate", "stock_id", "AdjustFactor"]],
    on=["jalaliDate", "stock_id"],
    how="outer",
)
gg = pdf.groupby("name")
pdf["AdjustFactor"] = gg["AdjustFactor"].fillna(method="ffill")
pdf = pdf[~pdf.date.isnull()]
pdf["AdjustFactor"] = pdf.AdjustFactor.fillna(1)

#%%
## Add issued shares to data
shrout = pd.read_csv(path + "shrout.csv")
mapdict = dict(zip(shrout.set_index(["name", "date"]).index, shrout.shrout))
i = "date"
pdf[i] = pdf[i].astype(int)

pdf["shrout"] = pdf.set_index(["name", "date"]).index.map(mapdict)
i = "stock_id"
shrout[i] = shrout[i].astype(str)
mapdict = dict(zip(shrout.set_index(["stock_id", "date"]).index, shrout.shrout))
pdf["shrout2"] = pdf.set_index(["stock_id", "date"]).index.map(mapdict)
pdf.loc[pdf.shrout.isnull(), "shrout"] = pdf.loc[pdf.shrout.isnull()]["shrout2"]
pdf = pdf.drop(columns=["shrout2"])
gg = pdf.groupby("name")
pdf["shrout"] = gg["shrout"].fillna(method="ffill")
i = "volume"
pdf[i] = pdf[i].astype(float)
d = pd.DataFrame()
d = d.append(pdf)
gg = d.groupby("name")
d["shrout"] = gg["shrout"].fillna(method="bfill")
#%%
pdf = pd.DataFrame()
pdf = pdf.append(d[~d.shrout.isnull()])

i = "group_id"
pdf[i] = pdf[i].astype(float)
i = "close_price"
pdf[i] = pdf[i].astype(float)
i = "quantity"
pdf[i] = pdf[i].astype(float)


gg = pdf.groupby(["name"])
for i in range(-5, 6):
    pdf["Volume({})".format(-i)] = gg.volume.shift(i)
    pdf["price({})".format(-i)] = gg.close_price.shift(i)

for i in ["last_price", "open_price", "value", "quantity", "volume"]:
    print(i)
    pdf.loc[(pdf["Volume(-1)"] == 0) & (pdf["Volume(1)"] == 0), i] = 0
    pdf.loc[(pdf["Volume(-1)"] == 0) & (pdf["Volume(1)"] == 0), i] = 0
    pdf.loc[(pdf["Volume(-2)"] == 0) & (pdf["Volume(1)"] == 0), i] = 0
    pdf.loc[(pdf["Volume(-1)"] == 0) & (pdf["Volume(2)"] == 0), i] = 0
    pdf.loc[(pdf["Volume(-2)"] == 0) & (pdf["Volume(2)"] == 0), i] = 0
    pdf.loc[(pdf["Volume(-3)"] == 0) & (pdf["Volume(1)"] == 0), i] = 0
    pdf.loc[(pdf["Volume(-1)"] == 0) & (pdf["Volume(3)"] == 0), i] = 0
    pdf.loc[(pdf["Volume(-1)"] == 0) & (pdf["Volume(4)"] == 0), i] = 0
    pdf.loc[(pdf["Volume(-2)"] == 0) & (pdf["Volume(4)"] == 0), i] = 0
    pdf.loc[(pdf["Volume(-4)"] == 0) & (pdf["Volume(1)"] == 0), i] = 0
    pdf.loc[(pdf["Volume(-4)"] == 0) & (pdf["Volume(2)"] == 0), i] = 0


pList = [1.0, 1000.0, 100.0, 10.0]
pdf = pdf[~((pdf.close_price.isin(pList)) & (pdf.volume == 0))]

pdf["close"] = pdf.close_price / pdf.AdjustFactor
gg = pdf.groupby(["name"])
pdf["return"] = gg.close.pct_change() * 100
pdf["MarketCap"] = pdf.close_price * pdf.shrout
pdf["yclose"] = gg.close.shift()


i = "return"
pdf.loc[(pdf["Volume(-1)"] == 0) & (pdf["Volume(1)"] == 0), i] = 0
pdf.loc[(pdf["Volume(-1)"] == 0) & (pdf["Volume(1)"] == 0), i] = 0
pdf.loc[(pdf["Volume(-2)"] == 0) & (pdf["Volume(1)"] == 0), i] = 0
pdf.loc[(pdf["Volume(-1)"] == 0) & (pdf["Volume(2)"] == 0), i] = 0
pdf.loc[(pdf["Volume(-2)"] == 0) & (pdf["Volume(2)"] == 0), i] = 0
pdf.loc[(pdf["Volume(-3)"] == 0) & (pdf["Volume(1)"] == 0), i] = 0
pdf.loc[(pdf["Volume(-1)"] == 0) & (pdf["Volume(3)"] == 0), i] = 0
pdf.loc[(pdf["Volume(-1)"] == 0) & (pdf["Volume(4)"] == 0), i] = 0
pdf.loc[(pdf["Volume(-2)"] == 0) & (pdf["Volume(4)"] == 0), i] = 0
pdf.loc[(pdf["Volume(-4)"] == 0) & (pdf["Volume(1)"] == 0), i] = 0
pdf.loc[(pdf["Volume(-4)"] == 0) & (pdf["Volume(2)"] == 0), i] = 0
pdf.loc[(pdf["Volume(-1)"] == 0) & (pdf["price(-1)"].isin(pList)), i] = 0


pdf.describe()
#%%
pdf = pdf.drop(
    columns=[
        "Volume(5)",
        "price(5)",
        "Volume(4)",
        "price(4)",
        "Volume(3)",
        "price(3)",
        "Volume(2)",
        "price(2)",
        "Volume(1)",
        "price(1)",
        "Volume(0)",
        "price(0)",
        "Volume(-1)",
        "price(-1)",
        "Volume(-2)",
        "price(-2)",
        "Volume(-3)",
        "price(-3)",
        "Volume(-4)",
        "price(-4)",
        "Volume(-5)",
        "yclose",
        "price(-5)",
        "yclose",
    ]
)
pdf = pdf.rename(columns={"close": "AdjustedPrice"})
# %%
for i in [
    "max_price",
    "min_price",
    "close_price",
    "last_price",
    "open_price",
    "value",
    "volume",
    "quantity",
]:
    pdf[i] = pdf[i].astype(float)

#%%

pdf.to_parquet(path2 + "Cleaned_Stocks_Prices_1400-04-27" + ".parquet")
# %%
