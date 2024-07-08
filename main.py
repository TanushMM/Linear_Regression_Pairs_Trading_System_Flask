from flask import Flask, render_template, request, session
import requests
import csv
import json
import os
import urllib
from io import BytesIO
import base64
import statistics
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns 
sns.set()

fresh_start = True
cwd = os.getcwd()

nifty_50 = pd.read_csv(f"{cwd}/static/data/ind_nifty50list.csv")
nifty_auto = pd.read_csv(f"{cwd}/static/data/ind_niftyautolist.csv")
nifty_bank = pd.read_csv(f"{cwd}/static/data/ind_niftybanklist.csv")
nifty_it = pd.read_csv(f"{cwd}/static/data/ind_niftyitlist.csv")

app = Flask(__name__)
app.secret_key = '0bc27a4ce8a7cccc3ae4b09f62045119c959e9fd8c9c432b5e25750e6a393346'
app.config['UPLOAD_FOLDER'] = 'static/images'
app.config['SCRIPT_DATA'] = 'static/script_data'

@app.route("/", methods=['POST', 'GET'])
def home():
    return render_template('home.html') 


@app.route("/submit", methods=['POST'])
def api_form():
    if request.method == "POST":
        session['email'] = request.form['email']
        session['password'] = request.form['password']
        return render_template('api_form.html', email=session.get('email'))
 
@app.route("/authkeyform", methods=['POST'])
def auth_form():
    if request.method == "POST":
        session['apikey'] = request.form['apikey']
        session['secretkey'] = request.form['secretkey']
        rurl = urllib.parse.quote('https://127.0.0.1', safe='')
        key = session.get('apikey')
        url = f'https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={key}&redirect_uri={rurl}'
        session['url'] = url
        return render_template('auth_form.html', email=session.get('email'), link=session.get('url'))

@app.route("/date", methods=["POST"])
def date():
    if request.method == "POST":
        session['authkey'] = request.form['authkey']
        return render_template('date_form.html', email=session.get('email'))

@app.route("/indices", methods=["POST"])
def indices():
    if request.method == "POST":
        session['fromdate'] = request.form['fromdate']
        session['todate'] = request.form['todate']
        return render_template('indices_form.html', email=session.get('email'))

@app.route("/regression", methods=["POST"])
def regression():
    if request.method == "POST":
        selected_options = request.form.getlist('options')
        session['selected_options'] = selected_options

        def get_and_save_data_as_csv_from_selected_options():
            def get_data(file_name, symbol, to_date, from_date):
                def json_to_csv(json_data, csv_filename):
                    candles_data = json_data["data"]["candles"]

                    with open(csv_filename, mode='w', newline='') as csv_file:
                        writer = csv.writer(csv_file)
                        # Writing header
                        writer.writerow(['data__candles__001','data__candles__002','data__candles__003','data__candles__004','data__candles__005','data__candles__006','data__candles__007'])
                        # Writing data
                        for candle in candles_data:
                            writer.writerow(candle)
                
                url = 'https://api.upstox.com/v2/login/authorization/token'
                headers = {
                    'accept': 'application/json' ,
                    'Api-Version': '2.0' ,
                    'Content-Type': 'application/x-www-form-urlencoded' 
                }
                data ={
                    'code':session.get('authkey'),
                    'client_id':session.get('apikey'),
                    'client_secret':session.get('secretkey'),
                    'redirect_uri':'https://127.0.0.1',
                    'grant_type':'authorization_code'
                }
                requests.post(url, headers= headers, data=data)

                #Getting Data
                data_url = f"https://api.upstox.com/v2/historical-candle/{symbol}/day/{to_date}/{from_date}"
                payload={}
                headers = {
                'Accept': 'application/json'
                }
                response = requests.request("GET", data_url, headers=headers, data=payload)
                data = response.json()

                #saving into CSV
                data = json.dumps(data)
                data = json.loads(data)
                json_to_csv(data, f"{cwd}/static/script_data/"+file_name+".csv")

            for i in session.get("selected_options"):
                def return_file(i):
                    if i == '1':
                        return nifty_50
                    elif i == '2':
                        return nifty_bank
                    elif i == '4':
                        return nifty_auto
                    elif i == '3':
                        return nifty_it
                data = return_file(i)
                for j in range(data.shape[0]):
                    name = data["Symbol"][j]
                    isin = "NSE_EQ|" + data["ISIN Code"][j]
                    get_data(name, isin, session.get('todate'), session.get('fromdate'))
        get_and_save_data_as_csv_from_selected_options()

        def lr_pairs_trading_system(path):
            def get_file_data(directory):
                count = 0
                csv_path = []
                file_names = []
                path = f'{directory}'
                list_of_files = os.listdir(path)
                for file in list_of_files:
                    if '.csv' in file:
                        file_names.append(file)
                        csv_path.append(f'{directory}/{file}')
                        count+=1
                return count,file_names,csv_path
            
            def data_collection(file_data):
                count = file_data[0]
                name = file_data[1]
                path = file_data[2]
                compiled_data = {}
                
                for i in range(0,count):
                    if i == 0:
                        temp_data = pd.read_csv(f'{path[i]}')
                        compiled_data["Date"] = list(temp_data['data__candles__001'].values)
                        compiled_data[f'{name[i]}'] = list(temp_data['data__candles__005'].values)
                    else:
                        temp_data = pd.read_csv(f'{path[i]}')
                        compiled_data[f'{name[i]}'] = list(temp_data['data__candles__005'].values)
                data = pd.DataFrame(compiled_data)
                return data
            
            def create_pairs(file_data,compiled_data):
                column_count = compiled_data.shape[1]
                pairs = []
                
                for i in range(1,column_count):
                    for j in range(i+1,column_count):
                        temp_list = []
                        temp_list.append(file_data[1][i-1])
                        temp_list.append(file_data[1][j-1])
                        pairs.append(temp_list)
                length = len(pairs)
                return length,pairs
            
            def lr_and_error_scores(y,x,compiled_data):
                Y = compiled_data[f'{y}']
                X = compiled_data[f'{x}']
                X = sm.add_constant(X)
                model = sm.OLS(Y,X).fit()
                std_error = statistics.stdev(model.resid) # this is the standard deviation of the residuals
                std_error_intercept_and_slope = model.bse # standard error of intercept and slope
                error_ratio = std_error_intercept_and_slope['const'] / std_error
                return error_ratio
            
            def best_error_pairs_data(file_data,compiled_data,pairs_data):
                no_of_pairs = pairs_data[0]
                best_error_pairs = []
                
                for i in range(0, no_of_pairs):
                    temp_pair = []
                    stock_a = pairs_data[1][i][0]
                    stock_b = pairs_data[1][i][1]
                    a_b = lr_and_error_scores(stock_a, stock_b, compiled_data)
                    b_a = lr_and_error_scores(stock_b, stock_a, compiled_data)
                    
                    if a_b < b_a:
                        temp_pair.append(pairs_data[1][i][0])
                        temp_pair.append(pairs_data[1][i][1])
                        best_error_pairs.append(temp_pair)
                        
                    else:
                        temp_pair.append(pairs_data[1][i][1])
                        temp_pair.append(pairs_data[1][i][0])
                        best_error_pairs.append(temp_pair)
                return best_error_pairs
            
            def lr_adf_data(y,x,compiled_data, index):
                def adf_test(data):
                    model = adfuller(data)
                    return model[1]
                
                def standard_error_data(model):
                    std_err = statistics.stdev(model.resid)
                    return std_err
                
                def std_err_intercept(model):
                    return model.bse['const']
                
                Y = compiled_data[y]
                X = compiled_data[x]
                X = sm.add_constant(X)
                model = sm.OLS(Y,X).fit()
                slope = model.params[x]
                intercept = model.params['const']
                adf_p_value = adf_test(model.resid)
                standard_error = standard_error_data(model)
                z_score = model.resid[0]/statistics.stdev(model.resid)
                # z_score = today's residual / std dev of residuals 
                standard_error_of_intercept = std_err_intercept(model)
                current_day_residual = model.resid[0]
                
                return index,y,x,slope,intercept,standard_error_of_intercept,adf_p_value,z_score,current_day_residual,standard_error
            def compute_lr_values_and_adf_values(best_error_pairs,compiled_data):
                length = len(best_error_pairs)
                big_data = []
                
                for i in range(0,length):
                    stock_a = best_error_pairs[i][0]
                    stock_b = best_error_pairs[i][1]
                    lr_adf_data_values = lr_adf_data(stock_a,stock_b, compiled_data, i+1)
                    big_data.append(lr_adf_data_values)
                return big_data
            
            def check_shape(file_data, path): # this is for explicit checking [this program does not use this function]
                for i in range(file_data[0]):
                    data = pd.read_csv(f'{path}/{file_data[1][i]}')
                    print(f"{file_data[1][i]} has a shape of {data.shape}")
                     
            file_data = get_file_data(path)
            compiled_data = data_collection(file_data)
            pairs_data = create_pairs(file_data,compiled_data)
            best_error_pairs = best_error_pairs_data(file_data,compiled_data,pairs_data)
            big_data = compute_lr_values_and_adf_values(best_error_pairs, compiled_data)
            big_data_data_frame = pd.DataFrame(big_data,columns=['Serial No.','Stock_Y','Stock_X','Slope/Beta','Intercept','Standard Error of Intercept','adf_p_value','z_score (Today\'s Residual / standard_error )','Current Day Residual','standard_error (STD DEV of residuals)'])
            return big_data_data_frame, compiled_data
        
        analyzed_data, compiled_data = lr_pairs_trading_system(f"{cwd}/static/script_data")
        
        # generate_seaborn_plot() function is under development
        def generate_seaborn_plot(data):
            sns_plot = sns.lineplot(data=data)
            plt.xlabel('X-axis')
            plt.ylabel('Y-axis')
            plt.title('Seaborn Plot')
            buffer = BytesIO()
            plt.savefig(buffer, format='png')
            buffer.seek(0)
            image_png = buffer.getvalue()
            buffer.close()
            return base64.b64encode(image_png).decode('utf-8')
        
        return render_template('regression.html', email=session.get('email'), stat_data = analyzed_data, rows=analyzed_data.shape[0])
    

# @app.route("/chart/<name>", method=["POST"])
# def chart(name):
#     pass


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
