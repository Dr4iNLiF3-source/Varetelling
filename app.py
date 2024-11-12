from flask import Flask, request, jsonify, send_file, send_from_directory, render_template
import sqlite3
import logging
import requests
from bs4 import BeautifulSoup
import openpyxl
import datetime
import os

app = Flask(__name__)
UPLOAD_FOLDER = 'documents'  # e.g., 'uploads' or any directory path
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def search(upc_code, div_class):
    url = f"https://www.cellartracker.com/m/wines/search/upc?q={upc_code}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    cookies = {
        'User': 'Dr4iNLiF3',
        'PWHash': '802893d4bbc5ac18a53a1e1f4ba457c0'
    }

    try:
        # Send the POST request with headers and cookies
        response = requests.get(url, headers=headers, cookies=cookies)
        response.raise_for_status()

        # Parse the response content with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the div with the specified class
        div = soup.find('div', class_=div_class)
        if div:
            # Find the h3 tag inside the div
            h3 = div.find('h3')
            if h3:
                return h3.get_text(strip=True)
            else:
                return "NONE"
        else:
            return "NONE"

    except requests.exceptions.RequestException as e:
        return "NONE"
    
@app.route('/get_inventory', methods=['GET'])
def get_inventory():
    logging.info("Received request to get inventory")
    
    with sqlite3.connect("inventory.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT products.id, products.name, products.barcode, quantities.quantity FROM products INNER JOIN quantities ON products.id = quantities.product_id")
        inventory = cur.fetchall()
    
    logging.info("Inventory retrieved successfully")
    return jsonify(inventory)

@app.route('/check_barcode', methods=['POST'])
def check_barcode():
    data = request.get_json()
    barcode = data.get("barcode")
    logging.info(f"Received request to check barcode: {barcode}")
    
    with sqlite3.connect("inventory.db") as conn:
        cur = conn.cursor()
        
        # Check if barcode exists
        cur.execute("SELECT id, name FROM products WHERE barcode=?", (barcode,))
        product = cur.fetchone()
        
        if product:
            logging.info(f"Barcode {barcode} exists with product name: {product[1]}")
            return jsonify({"exists": True, "id": product[0], "name": product[1]})
        else:
            logging.info(f"Barcode {barcode} does not exist")
            search_result = search(barcode, "wine-result-data has-action")
            return jsonify({"exists": False, "name": search_result})
            
            
@app.route('/add_product', methods=['POST'])
def add_product():
    data = request.get_json()
    barcode = data.get("barcode")
    name = data.get("name")
    logging.info(f"Received request to add product with barcode: {barcode}, name: {name}")
    
    with sqlite3.connect("inventory.db") as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO products (barcode, name) VALUES (?, ?)", (barcode, name))
        conn.commit()
        cur.execute("SELECT id FROM products WHERE barcode=?", (barcode,))
        product_id = cur.fetchone()[0]
        cur.execute("INSERT INTO quantities (product_id, quantity) VALUES (?, ?)", (product_id, 1))
        conn.commit()
        
    
    logging.info(f"Product with barcode: {barcode}, name: {name} added successfully")
    return jsonify({"status": "added"})


@app.route('/get_database', methods=['GET'])
def get_database():
    logging.info("Received request to get database")
    
    with sqlite3.connect("inventory.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, barcode FROM products")
        products = cur.fetchall()
    
    logging.info("Database retrieved successfully")
    return jsonify(products)


@app.route('/add_quantity', methods=['POST'])
def add_quantity():
    data = request.get_json()
    product_id = data.get("product_id")
    quantity = data.get("quantity")
    logging.info(f"Received request to add quantity: {quantity} for product_id: {product_id}")
    
    with sqlite3.connect("inventory.db") as conn:
        cur = conn.cursor()
        # add quantity to quantities table where product_id exists
        cur.execute("SELECT product_id FROM quantities WHERE product_id=?", (product_id,))
        product = cur.fetchone()
        if not product:
            cur.execute("INSERT INTO quantities (product_id, quantity) VALUES (?, ?)", (product_id, quantity))
        else:
            cur.execute("UPDATE quantities SET quantity = quantity + ? WHERE product_id=?", (quantity, product_id))
        conn.commit()
    
    logging.info(f"Quantity: {quantity} added for product_id: {product_id}")
    return jsonify({"status": "quantity added"})

@app.route('/')
def index():
    # List all .xlsx files in the UPLOAD_FOLDER
    xlsx_files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if f.endswith('.xlsx')]
    return render_template('index.html', files=xlsx_files)

# Route to download a specific file
@app.route('/download/<filename>')
def download_file(filename):
    # Send the file from the directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/make_document', methods=['GET'])
def make_document():
    items = get_items()
    writetocell(items)
    # return static file to be downloaded
    # get the name of the current month and year
    # then save the file with the name "Inventory_{month}_{year}.xlsx"
    file="The Wine Bar - Varetelling - "+str(datetime.datetime.now().strftime("%B"))+" "+str(datetime.datetime.now().year)+".xlsx"
    response = send_file("documents/"+file, as_attachment=True)
    response.headers["Content-Disposition"] = f'attachment; filename="{file}"'
    logging.info(f"Sending file: {file}")
    return response

def get_items():
    logging.info("Getting inventory")
    try:
        with sqlite3.connect("inventory.db") as conn:
            cur = conn.cursor()
            cur.execute("SELECT products.id, products.name, quantities.quantity FROM products INNER JOIN quantities ON products.id = quantities.product_id")
            inventory = cur.fetchall()
    except requests.exceptions.RequestException as e:
        return "Error in getting inventory: " + str(e)
    return inventory

def writetocell(items):
    wb = openpyxl.load_workbook('dummy.xlsx')
    sheet = wb.active
    #change active page to Vin
    sheet = wb['Vin']
    last=0
    for index, item in enumerate(items):
        name = item[1]
        quantity = item[2]
        sheet['B'+str(index+5)] = name
        sheet['D'+str(index+5)] = quantity
        sheet['F'+str(index+5)] = '=D'+str(index+5)+'*E'+str(index+5)
        #save last index
        last=index+5

    #make Sum row bold
    sheet['B'+str(last+3)].font = openpyxl.styles.Font(bold=True)
    sheet['B'+str(last+3)] = 'SUM'
    sheet['D'+str(last+3)] = '=SUM(D5:D'+str(last)+')'
    sheet['E'+str(last+3)] = '=SUM(E5:E'+str(last)+')'
    sheet['F'+str(last+3)] = '=SUM(F5:F'+str(last)+')'
    logging.info("Saving inventory to Excel")
    file="documents/The Wine Bar - Varetelling - "+str(datetime.datetime.now().strftime("%B"))+" "+str(datetime.datetime.now().year)+".xlsx"
    wb.save(file)
    wb.close()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
