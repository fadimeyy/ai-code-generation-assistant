import re

# ─────────────────────────────────────────────────────────────────────────────
# BENCHMARK_CASES — 50 buggy Python snippets with manual known_issues
# known_issues: list of keyword strings the LLM review SHOULD mention
#               (at least one match per issue = True Positive)
# ─────────────────────────────────────────────────────────────────────────────

BENCHMARK_CASES = [
    # ── SECURITY / HIGH ───────────────────────────────────────────────────────
    {
        "id": "TC-01", "name": "SQL Injection", "category": "Security", "severity": "HIGH",
        "known_issues": [
            ["sql injection", "string concatenation", "parameterized", "user input"],
        ],
        "code": '''
import sqlite3
def get_user(username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchone()
'''
    },
    {
        "id": "TC-02", "name": "Hardcoded Password", "category": "Security", "severity": "HIGH",
        "known_issues": [
            ["hardcoded password", "hardcoded credential", "password string", "secret"],
            ["hardcoded", "api key", "api_key", "token"],
        ],
        "code": '''
DB_PASSWORD = "admin123"
API_KEY = "sk-abc123def456"
def connect_db():
    return connect(password=DB_PASSWORD)
'''
    },
    {
        "id": "TC-03", "name": "Command Injection", "category": "Security", "severity": "HIGH",
        "known_issues": [
            ["command injection", "os.system", "shell injection", "user input", "arbitrary command"],
            ["os.popen", "shell", "injection", "sanitize"],
        ],
        "code": '''
import os
def run_command(user_input):
    os.system("ls " + user_input)
    result = os.popen(user_input).read()
    return result
'''
    },
    {
        "id": "TC-04", "name": "Eval Usage", "category": "Security", "severity": "HIGH",
        "known_issues": [
            ["eval", "arbitrary code", "code injection", "dangerous"],
            ["exec", "arbitrary code", "code injection", "dangerous"],
        ],
        "code": '''
def calculate_expression(expr):
    return eval(expr)
def run_code(code_str):
    exec(code_str)
    return "done"
'''
    },
    {
        "id": "TC-05", "name": "Pickle Deserialization", "category": "Security", "severity": "HIGH",
        "known_issues": [
            ["pickle", "deserialization", "arbitrary code", "untrusted", "malicious"],
        ],
        "code": '''
import pickle
def load_model(path):
    with open(path, "rb") as f:
        model = pickle.load(f)
    return model
def save_session(data, path):
    with open(path, "wb") as f:
        pickle.dump(data, f)
'''
    },
    {
        "id": "TC-06", "name": "Hardcoded Secret in URL", "category": "Security", "severity": "HIGH",
        "known_issues": [
            ["hardcoded", "secret", "token", "credential", "api key"],
            ["url", "token", "exposed", "hardcoded"],
        ],
        "code": '''
import requests
SECRET_TOKEN = "ghp_abcdef123456"
def fetch_data():
    url = "https://api.example.com/data?token=mysecrettoken123"
    headers = {"Authorization": "Bearer " + SECRET_TOKEN}
    return requests.get(url, headers=headers)
'''
    },
    {
        "id": "TC-07", "name": "XML External Entity", "category": "Security", "severity": "HIGH",
        "known_issues": [
            ["xml", "xxe", "external entity", "xml injection", "expat", "defusedxml", "vulnerable"],
        ],
        "code": '''
import xml.etree.ElementTree as ET
def parse_xml(xml_string):
    tree = ET.fromstring(xml_string)
    return tree
'''
    },
    {
        "id": "TC-08", "name": "Subprocess Shell=True", "category": "Security", "severity": "HIGH",
        "known_issues": [
            ["shell=true", "shell injection", "subprocess", "shell", "injection"],
            ["shell=true", "command injection", "user input", "dangerous"],
        ],
        "code": '''
import subprocess
def run_script(script_name):
    result = subprocess.run(script_name, shell=True, capture_output=True)
    return result.stdout
def build_project(build_cmd):
    subprocess.call(build_cmd, shell=True)
'''
    },
    {
        "id": "TC-09", "name": "Weak Hash MD5", "category": "Security", "severity": "HIGH",
        "known_issues": [
            ["md5", "weak hash", "cryptographically", "sha256", "bcrypt", "insecure"],
        ],
        "code": '''
import hashlib
def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()
def verify_password(password, hashed):
    return hashlib.md5(password.encode()).hexdigest() == hashed
'''
    },
    {
        "id": "TC-10", "name": "YAML Load Unsafe", "category": "Security", "severity": "HIGH",
        "known_issues": [
            ["yaml.load", "unsafe", "yaml.safe_load", "arbitrary", "deserialization"],
        ],
        "code": '''
import yaml
def load_config(config_str):
    return yaml.load(config_str)
def load_config_file(path):
    with open(path) as f:
        return yaml.load(f)
'''
    },
    # ── SECURITY / MEDIUM ─────────────────────────────────────────────────────
    {
        "id": "TC-11", "name": "Insecure Random", "category": "Security", "severity": "MEDIUM",
        "known_issues": [
            ["random", "insecure", "cryptographic", "secrets", "not suitable", "predictable"],
        ],
        "code": '''
import random, string
def generate_token(length=16):
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))
def generate_otp():
    return random.randint(100000, 999999)
'''
    },
    {
        "id": "TC-12", "name": "Assert for Security", "category": "Security", "severity": "MEDIUM",
        "known_issues": [
            ["assert", "security", "disabled", "-O", "optimized", "bypass"],
        ],
        "code": '''
def transfer_money(amount, account):
    assert amount > 0, "Amount must be positive"
    assert account is not None, "Account required"
    assert len(account) == 10, "Invalid account"
    return {"status": "ok", "amount": amount}
'''
    },
    {
        "id": "TC-13", "name": "Tempfile Insecure", "category": "Security", "severity": "MEDIUM",
        "known_issues": [
            ["temp", "predictable", "race condition", "tempfile", "/tmp", "insecure"],
        ],
        "code": '''
import os, tempfile
def write_temp(data):
    tmpfile = "/tmp/myapp_" + str(os.getpid())
    with open(tmpfile, "w") as f:
        f.write(data)
    return tmpfile
'''
    },
    {
        "id": "TC-14", "name": "HTTP Instead of HTTPS", "category": "Security", "severity": "MEDIUM",
        "known_issues": [
            ["http", "https", "insecure", "tls", "ssl", "plaintext", "unencrypted"],
        ],
        "code": '''
import urllib.request
def fetch_page(url):
    response = urllib.request.urlopen("http://api.example.com/data")
    return response.read()
'''
    },
    {
        "id": "TC-15", "name": "Binding to All Interfaces", "category": "Security", "severity": "MEDIUM",
        "known_issues": [
            ["0.0.0.0", "all interface", "binding", "network", "exposed", "localhost"],
        ],
        "code": '''
import socket
def start_server(port):
    s = socket.socket()
    s.bind(("0.0.0.0", port))
    s.listen(5)
    return s
'''
    },
    # ── QUALITY / MEDIUM ──────────────────────────────────────────────────────
    {
        "id": "TC-16", "name": "Bare Exception", "category": "Quality", "severity": "MEDIUM",
        "known_issues": [
            ["bare except", "except:", "broad exception", "silences", "swallows", "pass"],
        ],
        "code": '''
def read_file(path):
    try:
        with open(path) as f:
            return f.read()
    except:
        pass
def parse_json(data):
    try:
        import json
        return json.loads(data)
    except:
        return None
'''
    },
    {
        "id": "TC-17", "name": "Mutable Default Argument", "category": "Quality", "severity": "MEDIUM",
        "known_issues": [
            ["mutable default", "default argument", "list as default", "dict as default", "shared"],
        ],
        "code": '''
def add_item(item, items=[]):
    items.append(item)
    return items
def process(data, config={}):
    config["processed"] = True
    return data, config
'''
    },
    {
        "id": "TC-18", "name": "Missing Return Value", "category": "Quality", "severity": "MEDIUM",
        "known_issues": [
            ["missing return", "no return", "returns none", "implicit none", "divide"],
            ["undefined", "nameerror", "uninitialized", "name"],
        ],
        "code": '''
def divide(a, b):
    if b == 0:
        print("Cannot divide by zero")
    else:
        result = a / b
def get_name(user):
    if user:
        name = user["name"]
    return name
'''
    },
    {
        "id": "TC-19", "name": "Undefined Variable Risk", "category": "Quality", "severity": "MEDIUM",
        "known_issues": [
            ["undefined", "uninitialized", "nameerror", "not defined", "result", "before assignment"],
        ],
        "code": '''
def process_items(items):
    for item in items:
        if item > 0:
            result = item * 2
    return result

def get_value(flag):
    if flag:
        value = 42
    print(value)
'''
    },
    {
        "id": "TC-20", "name": "Global Variable Misuse", "category": "Quality", "severity": "MEDIUM",
        "known_issues": [
            ["global", "global variable", "avoid global", "side effect", "shared state"],
        ],
        "code": '''
counter = 0
data_cache = []

def increment():
    global counter
    counter += 1

def add_to_cache(item):
    global data_cache
    data_cache.append(item)
    return data_cache
'''
    },
    {
        "id": "TC-21", "name": "Infinite Loop Risk", "category": "Quality", "severity": "MEDIUM",
        "known_issues": [
            ["infinite loop", "no timeout", "hang", "deadlock", "while true", "termination"],
        ],
        "code": '''
def wait_for_result(check_fn):
    while True:
        result = check_fn()
        if result:
            break
    return result

def retry_forever(fn):
    while not fn():
        pass
'''
    },
    {
        "id": "TC-22", "name": "String Concatenation in Loop", "category": "Quality", "severity": "MEDIUM",
        "known_issues": [
            ["string concatenation", "loop", "join", "inefficient", "performance", "quadratic"],
        ],
        "code": '''
def build_html(items):
    result = ""
    for item in items:
        result = result + "<li>" + item + "</li>"
    return "<ul>" + result + "</ul>"
'''
    },
    {
        "id": "TC-23", "name": "Catching Exception Too Broad", "category": "Quality", "severity": "MEDIUM",
        "known_issues": [
            ["broad exception", "except exception", "too broad", "specific exception", "narrow"],
        ],
        "code": '''
def safe_divide(a, b):
    try:
        return a / b
    except Exception:
        return 0

def load_data(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception as e:
        print(e)
        return None
'''
    },
    {
        "id": "TC-24", "name": "Unreachable Code", "category": "Quality", "severity": "MEDIUM",
        "known_issues": [
            ["unreachable", "dead code", "never executed", "after return", "never runs"],
        ],
        "code": '''
def get_status(code):
    if code == 200:
        return "OK"
    elif code == 404:
        return "Not Found"
    else:
        return "Unknown"
    print("This never runs")

def calculate(x):
    return x * 2
    x = x + 1
'''
    },
    {
        "id": "TC-25", "name": "Division Without Zero Check", "category": "Quality", "severity": "MEDIUM",
        "known_issues": [
            ["division", "zero", "zerodivision", "divide by zero", "check", "empty"],
        ],
        "code": '''
def average(numbers):
    return sum(numbers) / len(numbers)

def percentage(part, total):
    return (part / total) * 100
'''
    },
    # ── QUALITY / LOW ─────────────────────────────────────────────────────────
    {
        "id": "TC-26", "name": "Magic Numbers", "category": "Quality", "severity": "LOW",
        "known_issues": [
            ["magic number", "hardcoded number", "constant", "named constant", "85000", "40000"],
        ],
        "code": '''
def calculate_tax(salary):
    if salary > 85000:
        return salary * 0.35
    elif salary > 40000:
        return salary * 0.22
    else:
        return salary * 0.12
'''
    },
    {
        "id": "TC-27", "name": "Too Long Function", "category": "Quality", "severity": "LOW",
        "known_issues": [
            ["long function", "too many", "refactor", "single responsibility", "complex", "steps"],
        ],
        "code": '''
def process_everything(data, config, mode, flag, extra=None):
    step1 = data * 2
    step2 = step1 + config.get("offset", 0)
    step3 = step2 if flag else step2 * -1
    step4 = step3 + (extra or 0)
    step5 = step4 / (config.get("divisor", 1) or 1)
    step6 = round(step5, 2)
    step7 = str(step6)
    step8 = step7.zfill(10)
    step9 = step8.strip()
    step10 = step9 if mode == "str" else float(step9)
    return step10
'''
    },
    {
        "id": "TC-28", "name": "Comparison to None/True/False", "category": "Quality", "severity": "LOW",
        "known_issues": [
            ["== none", "is none", "is not none", "comparison to none", "== true", "== false", "is true", "is false"],
        ],
        "code": '''
def check(value, flag):
    if value == None:
        return False
    if flag == True:
        return True
    if flag == False:
        return None
    return value
'''
    },
    {
        "id": "TC-29", "name": "Implicit String Concatenation", "category": "Quality", "severity": "LOW",
        "known_issues": [
            ["implicit", "string concatenation", "adjacent", "intentional", "confusing"],
        ],
        "code": '''
message = ("Hello, "
           "World! "
           "How are you?")

error_msg = ("Error: "
             "Something went wrong.")
'''
    },
    {
        "id": "TC-30", "name": "Shadowing Builtin", "category": "Quality", "severity": "LOW",
        "known_issues": [
            ["shadow", "builtin", "overrides", "built-in", "list", "dict", "type", "filter", "map"],
        ],
        "code": '''
def process(list, dict, type, input):
    id = 42
    filter = [x for x in list if x > 0]
    map = {k: v for k, v in dict.items()}
    return filter, map
'''
    },
    # ── STYLE / LOW ───────────────────────────────────────────────────────────
    {
        "id": "TC-31", "name": "Unused Imports", "category": "Style", "severity": "LOW",
        "known_issues": [
            ["unused import", "not used", "imported but unused", "remove import"],
            ["unused variable", "unused", "never used"],
        ],
        "code": '''
import os, sys, json, re
import math
from datetime import datetime, timedelta

def calculate(x, y):
    unused_var = 42
    result = x + y
    return result
'''
    },
    {
        "id": "TC-32", "name": "Wildcard Import", "category": "Style", "severity": "LOW",
        "known_issues": [
            ["wildcard", "import *", "star import", "namespace", "explicit"],
            ["long line", "line too long", "exceeds", "character", "pep 8"],
        ],
        "code": '''
from os import *
from sys import *

def very_long_function_name_that_does_something_important(parameter_one, parameter_two, parameter_three, parameter_four):
    x = 1 + 2
    y = x * 3
    return y
'''
    },
    {
        "id": "TC-33", "name": "Missing Whitespace", "category": "Style", "severity": "LOW",
        "known_issues": [
            ["whitespace", "spacing", "pep 8", "operator", "after comma", "style"],
        ],
        "code": '''
def add(a,b):
    return a+b

def multiply(x,y,z):
    result=x*y*z
    return result

x=10
y=20
z=x+y
'''
    },
    {
        "id": "TC-34", "name": "Inconsistent Return", "category": "Style", "severity": "LOW",
        "known_issues": [
            ["inconsistent return", "return none", "missing return", "implicit none", "consistent"],
        ],
        "code": '''
def find_item(items, target):
    for i, item in enumerate(items):
        if item == target:
            return i
    return

def check_value(x):
    if x > 0:
        return True
    elif x < 0:
        return False
'''
    },
    {
        "id": "TC-35", "name": "Long Lines", "category": "Style", "severity": "LOW",
        "known_issues": [
            ["long line", "line too long", "exceeds", "79", "88", "character", "pep 8"],
        ],
        "code": '''
def process_data(data, config, mode, debug=False, verbose=False, output_format="json", encoding="utf-8", timeout=30):
    result = {"data": data, "config": config, "mode": mode, "debug": debug, "verbose": verbose, "format": output_format, "encoding": encoding, "timeout": timeout}
    return result
'''
    },
    {
        "id": "TC-36", "name": "Missing Docstrings", "category": "Style", "severity": "LOW",
        "known_issues": [
            ["docstring", "documentation", "missing doc", "no docstring", "document"],
        ],
        "code": '''
class UserManager:
    def __init__(self, db):
        self.db = db

    def create_user(self, username, email, password):
        user = {"username": username, "email": email, "password": password}
        self.db.insert(user)
        return user

    def delete_user(self, user_id):
        self.db.delete(user_id)
'''
    },
    {
        "id": "TC-37", "name": "Trailing Whitespace & Blank Lines", "category": "Style", "severity": "LOW",
        "known_issues": [
            ["trailing whitespace", "trailing space", "blank line", "extra blank", "whitespace"],
        ],
        "code": '''
def function_one():
    x = 1   
    y = 2   
    return x + y



def function_two():


    return 42
'''
    },
    {
        "id": "TC-38", "name": "Single Letter Variables", "category": "Style", "severity": "LOW",
        "known_issues": [
            ["single letter", "variable name", "descriptive", "meaningful name", "naming"],
        ],
        "code": '''
def transform(d):
    r = []
    for i, v in enumerate(d):
        if v > 0:
            r.append(v * 2)
    return r

def calc(a, b, c, d, e):
    return a + b - c * d / e
'''
    },
    # ── MIXED ─────────────────────────────────────────────────────────────────
    {
        "id": "TC-39", "name": "SQL + Unused Imports Mixed", "category": "Security", "severity": "HIGH",
        "known_issues": [
            ["sql injection", "string concatenation", "parameterized", "user input"],
            ["unused import", "not used", "imported but unused"],
        ],
        "code": '''
import sqlite3, os, sys, re, json

def search_products(query, limit):
    conn = sqlite3.connect("shop.db")
    sql = "SELECT * FROM products WHERE name LIKE '%" + query + "%' LIMIT " + str(limit)
    return conn.execute(sql).fetchall()
'''
    },
    {
        "id": "TC-40", "name": "Password in Log", "category": "Security", "severity": "HIGH",
        "known_issues": [
            ["password", "log", "credential", "sensitive", "logging", "expose"],
        ],
        "code": '''
import logging
logger = logging.getLogger(__name__)

def login(username, password):
    logger.debug(f"Login attempt: user={username}, pass={password}")
    if authenticate(username, password):
        logger.info(f"User {username} logged in with password {password}")
        return True
    return False
'''
    },
    {
        "id": "TC-41", "name": "Race Condition File", "category": "Quality", "severity": "MEDIUM",
        "known_issues": [
            ["race condition", "toctou", "time of check", "atomic", "exists", "concurrent"],
        ],
        "code": '''
import os

def safe_write(path, data):
    if os.path.exists(path):
        os.remove(path)
    with open(path, "w") as f:
        f.write(data)

def check_and_create(path):
    if not os.path.exists(path):
        open(path, "w").close()
'''
    },
    {
        "id": "TC-42", "name": "Resource Leak", "category": "Quality", "severity": "MEDIUM",
        "known_issues": [
            ["resource leak", "file not closed", "context manager", "with statement", "open", "close"],
        ],
        "code": '''
def read_data(path):
    f = open(path)
    data = f.read()
    return data

def write_log(path, message):
    log = open(path, "a")
    log.write(message + "\\n")
'''
    },
    {
        "id": "TC-43", "name": "Type Confusion", "category": "Quality", "severity": "MEDIUM",
        "known_issues": [
            ["type", "typeerror", "string", "integer", "comparison", "conversion", "cast"],
        ],
        "code": '''
def add_values(a, b):
    return a + b

def process_input(user_input):
    value = user_input
    result = value * 2 + 1
    return result

def parse_age(age_str):
    age = age_str
    if age > 18:
        return "adult"
    return "minor"
'''
    },
    {
        "id": "TC-44", "name": "Circular Import Risk", "category": "Quality", "severity": "LOW",
        "known_issues": [
            ["circular import", "dynamic import", "__import__", "import inside function", "module"],
        ],
        "code": '''
from __future__ import annotations
import sys

def get_module(name):
    if name in sys.modules:
        return sys.modules[name]
    __import__(name)
    return sys.modules[name]
'''
    },
    {
        "id": "TC-45", "name": "Deprecated Function", "category": "Quality", "severity": "LOW",
        "known_issues": [
            ["deprecated", "removed", "cgi", "imp", "distutils", "obsolete", "replace"],
        ],
        "code": '''
import cgi
import imp
import distutils.core

def parse_form():
    form = cgi.FieldStorage()
    return form

def load_module(name):
    return imp.load_module(name, None, None, None)
'''
    },
    {
        "id": "TC-46", "name": "Insecure Deserialization JSON", "category": "Security", "severity": "MEDIUM",
        "known_issues": [
            ["marshal", "deserialization", "arbitrary", "unsafe", "untrusted"],
        ],
        "code": '''
import json
import marshal

def load_user_data(raw):
    return json.loads(raw)

def load_binary_data(raw):
    return marshal.loads(raw)
'''
    },
    {
        "id": "TC-47", "name": "Unvalidated Redirect", "category": "Security", "severity": "MEDIUM",
        "known_issues": [
            ["unvalidated redirect", "open redirect", "next", "validate", "whitelist", "trusted"],
        ],
        "code": '''
def get_redirect_url(request):
    next_url = request.args.get("next", "/")
    return next_url

def redirect_after_login(user, next_page):
    if user.is_authenticated:
        return redirect(next_page)
    return redirect("/login")
'''
    },
    {
        "id": "TC-48", "name": "Print Debugging Left In", "category": "Style", "severity": "LOW",
        "known_issues": [
            ["print", "debug", "logging", "production", "remove", "console"],
        ],
        "code": '''
def calculate_total(items):
    print("DEBUG: items =", items)
    total = sum(items)
    print("DEBUG: total =", total)
    print(f"Processing {len(items)} items")
    return total
'''
    },
    {
        "id": "TC-49", "name": "No Input Validation", "category": "Quality", "severity": "MEDIUM",
        "known_issues": [
            ["input validation", "validate", "sanitize", "no validation", "unchecked", "injection"],
        ],
        "code": '''
def create_user(username, email, age, role):
    user = {
        "username": username,
        "email": email,
        "age": age,
        "role": role
    }
    db.insert("users", user)
    return user

def update_balance(user_id, amount):
    db.update("accounts", {"balance": amount}, {"id": user_id})
'''
    },
    {
        "id": "TC-50", "name": "Regex DoS Vulnerability", "category": "Security", "severity": "HIGH",
        "known_issues": [
            ["redos", "regex dos", "denial of service", "catastrophic backtracking", "regex", "pattern"],
        ],
        "code": '''
import re

def validate_email(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+[.][a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))

def validate_username(username):
    pattern = r"^[a-zA-Z0-9_]{3,20}$"
    return bool(re.match(pattern, username))
'''
    },
    # ── REPO+LLM ONLY — cross-module / context-dependent cases ───────────────
    # Bu vakalar tek başına masum görünür; anlamlı bulgu için repo bağlamı şart.
    # repo_context alanı, LLM'e "diğer modüllerden gelen" sahte bağlam sağlar.
    {
        "id": "TC-R01",
        "name": "Unsafe Config Reuse Across Modules",
        "category": "Security",
        "severity": "HIGH",
        "repo_only": True,
        "repo_context": """\
# config.py
DB_PASSWORD = "prod_secret_123"
DEBUG = True
ALLOWED_HOSTS = ["*"]
SECRET_KEY = "django-insecure-abc123xyz"

# utils.py
from config import DB_PASSWORD, SECRET_KEY
def get_connection_string():
    return f"postgresql://admin:{DB_PASSWORD}@db:5432/prod"
""",
        "known_issues": [
            ["hardcoded password", "hardcoded credential", "secret", "config", "environment variable"],
            ["debug", "debug=true", "production", "insecure", "secret key"],
            ["allowed_hosts", "wildcard", "all hosts", "*"],
        ],
        "code": '''\
from config import DB_PASSWORD, SECRET_KEY, DEBUG

def init_app(app):
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["DEBUG"] = DEBUG
    return app
''',
    },
    {
        "id": "TC-R02",
        "name": "Shared Mutable State Between Services",
        "category": "Quality",
        "severity": "HIGH",
        "repo_only": True,
        "repo_context": """\
# cache.py
_cache = {}   # module-level shared dict, not thread-safe

def set_value(key, value):
    _cache[key] = value

def get_value(key):
    return _cache.get(key)

# worker.py
from cache import set_value, get_value
import threading

def process_job(job_id, data):
    set_value(job_id, data)          # multiple threads write simultaneously
    result = get_value(job_id)
    return result
""",
        "known_issues": [
            ["thread safety", "race condition", "shared state", "concurrent", "mutable"],
            ["module-level", "global", "shared dict", "not thread-safe", "lock"],
        ],
        "code": '''\
from cache import set_value, get_value

def handle_request(request_id, payload):
    set_value(request_id, payload)
    return get_value(request_id)
''',
    },
    {
        "id": "TC-R03",
        "name": "Auth Bypass via Module Import Order",
        "category": "Security",
        "severity": "HIGH",
        "repo_only": True,
        "repo_context": """\
# auth.py
_authenticated_users = set()

def login(user_id):
    _authenticated_users.add(user_id)

def is_authenticated(user_id):
    return user_id in _authenticated_users

# admin.py  ← imported BEFORE auth is initialised in some entry points
from auth import is_authenticated

def get_admin_panel(user_id):
    # relies on is_authenticated but never calls login first in test env
    if is_authenticated(user_id):
        return {"panel": "admin_data"}
    return {"error": "forbidden"}
""",
        "known_issues": [
            ["authentication", "bypass", "unauthenticated", "access control", "authorization"],
            ["import order", "initialisation", "state", "not validated", "missing check"],
        ],
        "code": '''\
from admin import get_admin_panel

def admin_route(request):
    user_id = request.get("user_id")
    return get_admin_panel(user_id)
''',
    },
    {
        "id": "TC-R04",
        "name": "Inconsistent Error Handling Across Layers",
        "category": "Quality",
        "severity": "MEDIUM",
        "repo_only": True,
        "repo_context": """\
# db_layer.py
def fetch_user(user_id):
    # raises KeyError if not found — undocumented
    result = _db[user_id]
    return result

# service_layer.py
from db_layer import fetch_user

def get_user_profile(user_id):
    user = fetch_user(user_id)   # KeyError propagates uncaught
    return {"name": user["name"], "email": user["email"]}
""",
        "known_issues": [
            ["exception handling", "uncaught", "propagates", "keyerror", "missing error handling"],
            ["inconsistent", "undocumented", "raises", "contract", "interface"],
        ],
        "code": '''\
from service_layer import get_user_profile

def user_endpoint(user_id):
    profile = get_user_profile(user_id)
    return profile
''',
    },
    {
        "id": "TC-R05",
        "name": "Circular Dependency & Late Import Side Effect",
        "category": "Quality",
        "severity": "MEDIUM",
        "repo_only": True,
        "repo_context": """\
# models.py
from services import send_welcome_email   # ← imports services at module load

class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email
        send_welcome_email(email)         # side-effect in __init__

# services.py
from models import User                   # ← circular: models imports services

def send_welcome_email(email):
    print(f"Welcome {email}")

def create_user(name, email):
    return User(name, email)
""",
        "known_issues": [
            ["circular import", "circular dependency", "import cycle", "models", "services"],
            ["side effect", "__init__", "constructor", "email in constructor", "unexpected"],
        ],
        "code": '''\
from services import create_user

def register(name, email):
    user = create_user(name, email)
    return {"status": "ok", "user": user.name}
''',
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# score_detection  — known_issues tabanlı (Ruff/Bandit bağımsız)
# ─────────────────────────────────────────────────────────────────────────────

def score_detection(
    llm_output: str,
    ruff_issues: list,
    bandit_issues: list,
    known_issues: list,
    mode: str,
) -> dict:
    """
    Ground-truth scoring using manually curated known_issues.

    known_issues: list of lists — each inner list is one issue with
                  alternative keyword phrases (any match = TP).

    Precision = TP / (TP + FP)
    Recall    = TP / total_GT
    F1        = harmonic mean
    """
    text = (llm_output or "").lower()
    total_gt = len(known_issues)

    if total_gt == 0:
        return {"tp": 0, "fp": 0, "fn": 0, "total_gt": 0,
                "precision": 0.0, "recall": 0.0, "f1": 0.0}

    # ── Count TPs: each known issue matched if ANY keyword found ──────────────
    tp = 0
    fn = 0
    for kw_list in known_issues:
        if any(kw.lower() in text for kw in kw_list):
            tp += 1
        else:
            fn += 1

    # ── Estimate FPs: lines with issue language beyond our GT ─────────────────
    _ISSUE_SIGNALS = [
        "issue", "problem", "bug", "error", "warning", "vulnerability",
        "insecure", "unsafe", "risk", "should", "avoid", "fix", "recommend",
        "concern", "danger", "critical", "severity", "line ", "high", "medium",
    ]
    issue_lines = [
        ln for ln in text.splitlines()
        if any(sig in ln for sig in _ISSUE_SIGNALS) and ln.strip()
    ]
    fp = max(0, len(issue_lines) - tp)

    precision = round(tp / (tp + fp) * 100, 1) if (tp + fp) > 0 else 0.0
    recall    = round(tp / total_gt * 100, 1)
    f1        = round(2 * precision * recall / (precision + recall), 1) \
                if (precision + recall) > 0 else 0.0

    return {
        "tp":        tp,
        "fp":        fp,
        "fn":        fn,
        "total_gt":  total_gt,
        "precision": precision,
        "recall":    recall,
        "f1":        f1,
    }