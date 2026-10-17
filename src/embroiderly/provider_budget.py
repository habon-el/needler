"""Fail-closed USD reservations shared by every billable assistant adapter.

Amounts are integer nanodollars, rounded upward. Timed-out requests retain their
full reservation; no automatic refund can free money already spent upstream.
"""
import copy
from datetime import datetime, timezone, date
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import json
import os
from pathlib import Path
import sqlite3
import urllib.request
from uuid import uuid4


class BudgetError(ValueError):
    pass


def money(value):
    try: amount=Decimal(str(value))
    except (InvalidOperation,ValueError): raise BudgetError('Budget amounts must be positive USD values.')
    if not amount.is_finite() or amount<=0:raise BudgetError('Both USD caps and model rates must be positive.')
    return int((amount*1_000_000_000).to_integral_value(rounding=ROUND_CEILING))


def policy_path(root):
    return Path(root)/'work'/'provider-budget.json'


def read_policy(root,model):
    try: policy=json.loads(policy_path(root).read_text())
    except (OSError,ValueError): raise BudgetError('Paid assistance is locked: configure per-design and monthly USD caps and verified model rates first.')
    try:
        caps=(money(policy['per_design_usd']),money(policy['per_month_usd']))
        rate=policy['models'][model]
        if rate['verified_by_user'] is not True or not rate['source_note'].strip():raise BudgetError('Confirm the model rates and their source first.')
        if date.fromisoformat(rate['valid_until'])<datetime.now(timezone.utc).date():raise BudgetError('Model pricing verification has expired; paid assistance is locked.')
        rates=(money(rate['input_usd_per_million']),money(rate['output_usd_per_million']))
    except (KeyError,TypeError,AttributeError): raise BudgetError('Both caps and verified rates for this exact model are required.')
    return caps,rates


class BudgetLedger:
    def __init__(self,root,model):
        self.root=Path(root);self.model=model
        self.caps,self.rates=read_policy(root,model)  # gate before DB or network creation
        self.path=self.root/'work'/'provider-spend.sqlite3'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY,design TEXT NOT NULL,month TEXT NOT NULL,nanodollars INTEGER NOT NULL,model TEXT NOT NULL)')

    def reserve(self,design,input_tokens,output_tokens):
        if not isinstance(design,str) or not design.strip():raise BudgetError('A stable design identity is required for spending.')
        if any(type(n) is not int or n<0 for n in (input_tokens,output_tokens)) or not output_tokens:
            raise BudgetError('Exact input tokens and a bounded output limit are required.')
        self.caps,self.rates=read_policy(self.root,self.model)
        amount=(input_tokens*self.rates[0]+output_tokens*self.rates[1]+999_999)//1_000_000
        month=datetime.now(timezone.utc).strftime('%Y-%m');ident=uuid4().hex
        with sqlite3.connect(self.path,timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            used_design=db.execute('SELECT COALESCE(SUM(nanodollars),0) FROM reservations WHERE design=?',(design,)).fetchone()[0]
            used_month=db.execute('SELECT COALESCE(SUM(nanodollars),0) FROM reservations WHERE month=?',(month,)).fetchone()[0]
            if used_design+amount>self.caps[0]:raise BudgetError('This request would exceed the design’s USD budget. No generation request was sent.')
            if used_month+amount>self.caps[1]:raise BudgetError('This request would exceed the monthly USD budget. No generation request was sent.')
            db.execute('INSERT INTO reservations VALUES(?,?,?,?,?)',(ident,design,month,amount,self.model))
        return ident,amount


class BudgetedProvider:
    def __init__(self,root,design,model):
        self.ledger=BudgetLedger(root,model)
        self.design=design;self.model=model
        if not isinstance(design,str) or not design.strip():raise BudgetError('Design identity is required.')
        if not os.environ.get('OPENAI_API_KEY'):raise BudgetError('Model key is not configured. Manual tools remain available.')

    def _post(self,suffix,payload):
        req=urllib.request.Request('https://api.openai.com/v1/responses'+suffix,
            data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+os.environ['OPENAI_API_KEY']})
        with urllib.request.urlopen(req,timeout=45) as response:return json.load(response)

    def request(self,payload):
        if payload.get('model')!=self.model or payload.get('tools') or payload.get('background'):
            raise BudgetError('Only the verified model and tool-free foreground requests are allowed.')
        limit=payload.get('max_output_tokens')
        if type(limit) is not int or not 1<=limit<=10000:raise BudgetError('Set a bounded output-token limit.')
        # Count the same multimodal input and output schema; no heuristic token fallback.
        counted={key:copy.deepcopy(payload[key]) for key in ('model','input','instructions','text') if key in payload}
        result=self._post('/input_tokens',counted)
        count=result.get('input_tokens')
        if type(count) is not int or count<0:raise BudgetError('Provider did not return an exact input-token count. No generation request was sent.')
        self.ledger.reserve(self.design,count,limit)
        outgoing=copy.deepcopy(payload);outgoing['service_tier']='default';outgoing['store']=False
        # Full worst-case reservation remains charged even if usage is lower or unknown.
        return self._post('',outgoing)


def current_provider():
    """Route-owned design/root; client input cannot choose another budget bucket."""
    from flask import current_app, has_request_context, request
    if not has_request_context():raise BudgetError('A design-scoped request is required for paid assistance.')
    root=current_app.config['EMBROIDERLY_WORKSPACE']
    name=(request.view_args or {}).get('name')
    if not name:raise BudgetError('A design-scoped request is required.')
    return BudgetedProvider(root,name,os.environ.get('EMBROIDERLY_AI_MODEL',''))


def readiness():
    try:current_provider();return True,''
    except (BudgetError,ValueError) as error:return False,str(error)
