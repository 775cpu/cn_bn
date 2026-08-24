import binance.client
from decimal import Decimal
import sys;'qgb.U' in sys.modules or sys.path.append('/home/qgb/')
from qgb import py,U,T,N,F

gi16=B_intervals=('1M','1w','3d','1d','12h','8h','6h','4h','2h','1h','30m','15m','5m','3m','1m','1s')
gi15=B_intervals_future=B_intervals[:-1]
g5intervals=('1M','1d','1h','1m','1s')
gdiz={'1M': '1个月','1w': '1周','3d': '3天','1d': '1天','12h': '12小时','8h': '8小时','6h': '6小时','4h': '4小时','2h': '2小时','1h': '1小时','30m': '30分钟','15m': '15分钟','5m': '5分钟','3m': '3分钟','1m': '1分钟','1s': '1秒'}

gskip_future_symbols=['COMBOUSDT','BTCSTUSDT']
gskip_symbols_startswith=['VENUSDT','BNBBULL','BNBBEAR','LUNAUSDT','COMBOUSDT'
,'MAVUSDT','MAVTUSD','CFXTUSD']
gd_b_coingecko={'BTTC':'btt','IOTA':'miota'}
gsTimeFormat='%Y-%m-%d %H:%M:%S'
gtimedelta_second=U.time_delta(seconds=1)
gs_fdsdt='/home/qgb/test/fdsdt-440.dill'
gs_dsdt='/home/qgb/test/dsdt-1338.dill'

gclient=U.get('binance.client')
gdualSidePosition=False # False 单向持仓模式 ,   True 双向持仓模式
def set_client(client):
	global gclient,gdualSidePosition
	gclient=U.set('binance.client',client)
	gdualSidePosition=client.futures_get_position_mode()['dualSidePosition']
	return gclient
	# return U.set('binance.client',client)

def get_client(client=None):
	global gclient
	c0=U.get('binance.client')
	if client:
		if client==c0:return client
		if client.ping()=={}:return client
	else:
		gclient=c0
		return c0


def html(response,file,**ka):
	s=F.read(f'/home/qgb/bn/html/{file}.html')
	s=N.HTML.format(s,**ka)
	response.headers['Content-Type']='text/html;charset=utf-8'
	response.set_data(s)

def get_current_user_number3():
	dun3 = {
    204971825: 173,
    840380973: 151
	}
	uid=gclient.get_account()['uid']
	return dun3[uid]

	if uid==204971825:return 173
	elif uid==840380973:return 151
	else:raise EnvironmentError(f'Unexpected user uid:{uid}')

def spot_get_all_orders_return_dict():
	rd={}
	for ord in gclient.get_open_orders():
		s=ord['symbol']
		U.dict_add_value_list(rd,s,ord)
	return rd
get_spot_all_orders=spot_get_all_order_return_dict=spot_get_all_orders_return_dict

def futures_get_all_price_dict():
	import urllib,json
	urp = urllib.request.urlopen(f'https://fapi.binance.com/fapi/v1/ticker/price')
	data=urp.read().decode("utf-8")
	j=json.loads(data)
	 
	rd={}
	for d in j: # {"symbol": "BTCUSDT",      "price": "51630.00",     "time": 1708926521286}
		if d['symbol'] in rd:
			raise AssertionError(d)
		rd[d['symbol']]=Decimal(d['price'])
	return rd
futures_get_all_ticker=futures_get_all_price_dict


def is_base_TRADING(b,dsdq=None):
	if not dsdq:dsdq=get_exchange_info_by_name('dsdq')
	dst={}
	for s,d in dsdq.items():
		if d['baseAsset']==b:
			if d['status']=='TRADING':
				return s
			dst[s]=d['status']
	if not dst:return py.No(b+' Not found in dsdq')		
	return py.No(dst)

def futures_renew_short_order(symbol='',price=0,last_order=None,limit_notional=22,create_if_not_exist=False,client=None):
	'''{'orderId': 2568797159,
 'status': 'NEW',
 'clientOrderId': 'kwwlpHUMESHnRrf9ANozX8',
 'avgPrice': '0',
 'origQty': '14',
 'executedQty': '0',
 'cumQuote': '0.00000',
 'timeInForce': 'GTC',
 'type': 'LIMIT',
 'reduceOnly': False,
 'closePosition': False,
 'side': 'SELL',
 'positionSide': 'SHORT',
 'stopPrice': '0',
 'workingType': 'CONTRACT_PRICE',
 'priceProtect': False,
 'origType': 'LIMIT',
 'priceMatch': 'NONE',
 'selfTradePreventionMode': 'NONE',
 'goodTillDate': 0,
 'time': 1707819914000,
 'updateTime': 1707394896898,
 'symbol': 'DUSKUSDT',
 'lastFundingRate': '0.00042673',
 'interestRate': '0.00010000',
 'nextFundingTime': 1707840000000,
 'price': '0.38000',
 'markPrice': '0.33658631',
 'markPrice_rate': Decimal('0.1290'),
 'indexPrice': '0.33608760',
 'indexPrice_rate': Decimal('0.1307'),
 'estimatedSettlePrice': '0.33482254',
 'estimatedSettlePrice_rate': Decimal('0.1349')}
	'''
	client=get_client(client)
	if not symbol:
		os=get_all_future_open_orders(return_cp=1,return_list=1)
		assert len(os)==1
		assert Decimal(price)>os[0]['cp']
		symbol=os[0]

	if py.isdict(symbol):
		assert not last_order
		last_order=symbol
		symbol=symbol['symbol']
	else:	
		symbol=futures_convert_symbol(symbol)
	cs=U.get_or_set(symbol+'.short.orders',collections.deque([], maxlen=99))
	xs=U.get_or_set(symbol+'.short.xs',collections.deque([], maxlen=99))
	if not last_order and not cs:
		ords=get_all_future_open_orders(symbol,side='SELL',return_cp=1,return_list=1)
		if not create_if_not_exist:
			assert len(ords)>0,f'not exists {symbol!r} order , try create_if_not_exist ?'
			last_order=ords[0]
		# 不能加 ,positionSide='SHORT'  ，单向持仓模式下 'positionSide': 'BOTH',
	if last_order:
		if py.isdict(last_order):
			if ('nextFundingTime' in last_order) and (last_order not in cs):
				cs.append(last_order)
			last_order=last_order['orderId']
	if cs and (not py.isint(last_order) or last_order<1):
		last_order=cs[-1]['orderId']

	if create_if_not_exist:
		try:
			x=client.futures_cancel_order(symbol=symbol,orderId=last_order)
			xs.append(x)
		except Exception as e:
			print(e)
			return futures_create_short_order_limit_price(symbol=symbol,price=price,limit_notional=limit_notional,renew=True)	
	else:
		try:x=client.futures_cancel_order(symbol=symbol,orderId=last_order)
		except binance.BinanceAPIException as e:
			if e.message=='Unknown order sent.':cs.clear() # 订单已被取消，不存在
			raise e
		xs.append(x)

	d=futures_create_short_order_limit_price(symbol=symbol,price=price,limit_notional=limit_notional,renew=True)
	return x,d
renew_futures_short_order=futures_renew_short_order


def futures_get_min_order_quantity(symbol,price=0,limit_notional=10,more=0,return_price=False,):
	if not price:
		price=futures_get_symbol_price(symbol)
	else:
		price=Decimal(price)
	if not price:raise py.ArgumentError(price)
	# dsdq,dsp=get_exchange_info_by_name('dsdq,dsp')

	d=U.get_or_dill_load(gs_fdsdt)[symbol]

	p,q,m=U.get_dict_multi_values_return_list(d,'tickSize','stepSize','minNotional',convert_function=Decimal)

	if more:
		m=m*Decimal(1+more)
	n=py.int(m/price)

	while n*price<m:
		n+=q
	if limit_notional and n*price>limit_notional:raise py.ArgumentError('limit_notional',n,price,n*price,limit_notional)

	if return_price:return n,price
	return n
get_future_min_qty=futures_get_min_qty=get_min_qty_futures=futures_get_min_order_quantity

def futures_round_price_quantity(symbol,price=None,quantity=None,d=None,client=None):
	if py.isdict(symbol):
		d=symbol
		symbol=d['baseAsset']+d['quoteAsset']
	if not d:
		# try: 
		d=U.get_or_dill_load(gs_fdsdt)[symbol]
		# except:
		# 	print(U.stime(),'round_price_quantity',get_exchange_info_by_name)	
		# 	d=get_exchange_info_by_name('dsdq',client=client)[symbol]
		# 	d['tickSize']=Decimal(d['tickSize']).normalize()
		# 	d['stepSize']=Decimal(d['stepSize']).normalize()	
	r=[]
	if price:
		price=Decimal(price)
		price=price.quantize(d['tickSize'])
		r.append(py.str(price))

	if quantity:
		quantity=Decimal(quantity)
		quantity=quantity.quantize(d['stepSize'])
		r.append(py.str(quantity))
		
	if py.len(r)==1:return r[0]
	return r
round_price_quantity_futures=futures_round_price_quantity

def round_price_quantity(symbol,price=None,quantity=None,d=None,func=py.str,client=None):
	''' price support list'''
	if py.isdict(symbol):
		d=symbol
		symbol=d['baseAsset']+d['quoteAsset']
	if not d:
		try:
			d=U.get_or_dill_load(gs_dsdt)[symbol]
		except:
			print(U.stime(),'round_price_quantity','get_exchange_info_by_name except:',symbol)	
			d=get_exchange_info_by_name('dsdq',client=client)[symbol]
			d['tickSize']=Decimal(d['tickSize']).normalize()
			d['stepSize']=Decimal(d['stepSize']).normalize()
	r=[]
	if price:
		if U.iterable_but_str(price):
			for p in price:
				p=Decimal(p)
				p=p.quantize(d['tickSize'])
				r.append(func(p))
		else:		
			decimal_price=Decimal(price)
			pq=decimal_price.quantize(d['tickSize'])
			sp=func(pq)
			if py.istr(sp) and 'E' in sp:
				sp=py.format(pq, '0.8f')
			r.append(sp)

	if quantity:
		quantity=Decimal(quantity)
		quantity=quantity.quantize(d['stepSize'])
		r.append(func(quantity))
		
	if py.len(r)==1:return r[0]
	return r

def sell_spot_minNotional(symbol,price=None,quantity=None,renew=True,client=None):
	'''  '''
	client=get_client(client)
	dsdq,dsp,dbp=get_exchange_info_by_name('dsdq,dsp,dbp',client=client)
	p,q,m=U.get_dict_multi_values_return_list(dsdq[symbol],'tickSize','stepSize','minNotional',convert_function=Decimal)
	ds=get_spot_postion(dbp=dbp,client=client)
	for d in ds:
		if d['asset'] == dsdq[symbol]['baseAsset']:
			tp=(m/d['free'])+Decimal(dsdq[symbol]['tickSize'])
			assert tp>dsp[symbol]
			return create_spot_order_limit_price(symbol,*round_price_quantity(dsdq[symbol],tp,quantity=d['free']),more=0,renew=renew,side='SELL',client=client)

	raise Exception(symbol,'not found in B.get_spot_postion')

def ms_to_pandas_Timestamp(ms):
	import pandas
	return pandas.Timestamp(ms,unit='ms').tz_localize('UTC').tz_convert('Asia/Shanghai')

def get_futures_kline(symbol,interval='1M',start=0,end=None,limit=1000,convert_func=Decimal,proxies=None,**ka):
	if not convert_func:convert_func=lambda a:a
	if start:
		if py.istr(start) and start.startswith('startTime='):
			pass
		else:
			start=f'startTime={start}&'
	else:
		start=''

	if end:
		if py.istr(end) and end.startswith('endTime='):
			pass
		else:
			end=f'endTime={end}&'	
	else:
		end=''
	url=f'https://fapi.binance.com/fapi/v1/klines?{start}{end}interval={interval}&limit={limit}&symbol={symbol}'
	j=N.HTTP.get_json(url,proxies=proxies,**ka)
	if not py.islist(j):return py.No(j)
	for row in j:
		for n in [1,2,3,4,5,7,9,10]:
			row[n]=convert_func(row[n])
	return j
get_kline_futures=get_futures_kline	

def get_kline_without_pandas(symbol,interval='1d',start=0,end=None,limit=1000,convert_func=Decimal,
convert_OpenTime=False,convert_CloseTime=False,proxies=None,**ka):
	if not convert_func:convert_func=lambda a:a
	if start:
		if py.istr(start) and start.startswith('startTime='):
			pass
		else:
			start=f'startTime={start}&'
	else:
		start=''

	if end:
		if py.istr(end) and end.startswith('endTime='):
			pass
		else:
			end=f'endTime={end}&'	
	else:
		end=''

		
	url=f'https://api.binance.com/api/v3/klines?{start}{end}interval={interval}&limit={limit}&symbol={symbol}'
	j=N.HTTP.get_json(url,proxies=proxies,**ka)
	if not py.islist(j):return py.No(j)
	for row in j:
		for n in [1,2,3,4,5,7,9,10]:
			row[n]=convert_func(row[n])
		if convert_OpenTime:
			row[0]=ms_to_pandas_Timestamp(row[0])
		if convert_CloseTime:
			row[6]=ms_to_pandas_Timestamp(row[6])
			# import pandas
			# row[0]=pandas.Timestamp(row[0],unit='ms').tz_localize('UTC').tz_convert('Asia/Shanghai')
	return j

def get_kline_min_without_pandas(symbol,start=0,intervals_limit_dict=dict(M=999,d=32,h=24,m=60,s=60),convert_OpenTime=False,convert_EndTime=False,return_all_json=False,proxies=None,**ka):
	if return_all_json:dij={}
	end=py.int('9'*13)
	for interval,limit in intervals_limit_dict.items(): #['1M','1d','1h','1m','1s']:
		interval='1'+interval
		if interval!='1M' and start:start=0

		j=get_kline_without_pandas(symbol=symbol,interval=interval,start=start,end=end,limit=limit,convert_OpenTime=convert_OpenTime,proxies=proxies,**ka)
		j.sort(key=lambda x:x[3],reverse=False)# min to max
		# return j
		end=j[0][6]
		if convert_EndTime:
			for row in j:
				row[6]=ms_to_pandas_Timestamp(row[6])

		if return_all_json:dij[interval]=j

	if return_all_json:return dij
				
	return j[0]
get_min_without_pandas=get_kline_min_without_pandas

def get_kline_first_second(symbol,client=None,return_month_len=False,return_all_json=False,**ka):
	client=get_client(client)
	def _return():
		ms=dij['1s'][0][0]
		if return_all_json:
			return dij
		if return_month_len:
			return ms,mn
		return ms
	end=U.itime_ms()
	dij={}
	for interval,limit in dict(M=999,d=32,h=24,m=60,s=60).items(): #['1M','1d','1h','1m','1s']:
		interval='1'+interval
		j=N.HTTP.get_json(f'https://api.binance.com/api/v3/klines?endTime={end}&interval={interval}&limit={limit}&symbol={symbol}',**ka)
		end=j[0][6]
		dij[interval]=j
		if interval=='1M':
			mn=len(j)
			
	return _return()

def pandas_abb(a,b,round=None):
	''' pandas.core.series.Series'''
	import numpy
	result = (a - b) / b
    # 将b中小于0的位置的结果设为NaN
	result = result.mask(b < 0, numpy.inf)
	return result

def a_b_b(a,b,round=None):
	a=Decimal(a)
	b=Decimal(b)
	if b<=0:return 9999_9999
	r=(a-b)/b
	if round and py.isint(round):r=py.round(r,round)
	return r
abb=get_rate=a_b_b

def get_din_last_is_n(din,h,l):
	return 

def get_last_is_max_n(y,value=None,m=None):
	if not value:value=y[-1]
	if not m:m=py.len(y)
	for i in range(1,m):
		if y[-i]>value:  # 不用= ,防止和自身做比较
			return i
	return m
last_max_n=get_last_is_max_n

def get_last_is_min_n(y,value=None,m=None):
	if not value:value=y[-1]
	if not m:m=py.len(y)
	for i in range(1,m):
		if y[-i]<value:
			return i
	return m
last_min_n=get_last_is_min_n

gdefault_more=0.05
def get_min_order_quantity(symbol,price=0,more=0,dq=None):
	if price:
		price=Decimal(price)
	else:	
		dsdq,dsp=get_exchange_info_by_name('dsdq,dsp')
		price=dsp[symbol]
		if not dq:dq=dsdq[symbol]

	if not dq:
		dsdq=get_exchange_info_by_name('dsdq')
		dq=dsdq[symbol]

	p,q,m=U.get_dict_multi_values_return_list(dq,'tickSize','stepSize','minNotional',convert_function=Decimal)
	
	if not price:raise py.ArgumentError(price)

	if more:
		m=m*Decimal(1+more)

	n=py.int(m/price)

	while n*price<m:
		n+=q
	# for i in range(1,99999):
	# 	else:
	# 		break 
	return n
get_min_qty=get_min_order_quantity

def create_spot_order_limit_price(symbol,price,quantity=None,more=gdefault_more,renew=True,side='BUY',client=None):
	'''  下单价格超过现价5倍   BinanceAPIException: APIError(code=-1013): Filter failure: PERCENT_PRICE_BY_SIDE 
	'''
	client=get_client(client)
	symbol=spot_convert_symbol(symbol)
	if side=='SELL' and more==gdefault_more:more=0
	if not quantity:
		quantity=get_min_order_quantity(symbol,price=price,more=more)
	price=round_price_quantity(symbol,price=price)	
	try:
		d=client.create_order(symbol=symbol,side=side,type='LIMIT',timeInForce='GTC',quantity=quantity,price=price)
	except Exception as e:
		print(U.v.client.create_order(symbol=symbol,side=side,type='LIMIT',timeInForce='GTC',quantity=quantity,price=price))	
		raise e
	d['_notional']=Decimal(quantity)*Decimal(price)
	if renew:
		if side=='SELL':
			cs=U.get_or_set(symbol+'.SELL.orders',[])
			cs.append(d)
			U.set(symbol+'.SELL.price',Decimal(d['price']))
		if side=='BUY':
			cs=U.get_or_set(symbol+'.BUY.orders',[])
			cs.append(d)
			U.set(symbol+'.BUY.price',Decimal(d['price']))
	return d	
create_order=create_spot_order_limit_price

def create_spot_order_oco(symbol, price,stop_price=0,stop_limit_price=0, quantity=None, more=py.No('auto'),renew=True, side='SELL', client=None):
	''' stop_price 触发价格 
币余额不足 BinanceAPIException: APIError(code=-2010): Account has insufficient balance for requested action.
'''
	client = get_client(client)
	symbol=spot_convert_symbol(symbol)
	if side=='SELL':
		if not stop_price:
			if stop_limit_price:stop_price=Decimal(stop_limit_price)*Decimal(0.999)
			else:
				fb=[d for d in client.get_all_orders(symbol=symbol) if d['status']=='FILLED' and d['side']=='BUY']
				if not fb:raise EnvironmentError('不可能没有购买记录啊，不然卖的币从哪里来')
				stop_price=Decimal(fb[-1]['price'])
		assert price>stop_price
		if not 	stop_limit_price:
			stop_limit_price=stop_price*Decimal(1.001)
		assert price>stop_limit_price	
		if not more:more=0
	else:# BUY
		if py.isno(more):more=0.05	
	if not quantity:
		quantity = get_min_order_quantity(symbol, price=stop_limit_price, more=more)

	price,stop_price,stop_limit_price= round_price_quantity(symbol,price=[price,stop_price,stop_limit_price],func=py.str)
	try:
		d = client.create_oco_order(symbol=symbol, side=side, quantity=quantity, price=price, stopPrice=stop_price, stopLimitPrice=stop_limit_price, stopLimitTimeInForce='GTC')
	except Exception as e:
		print(U.v.client.create_oco_order(symbol=symbol, side=side, quantity=quantity, price=price, stopPrice=stop_price, stopLimitPrice=stop_limit_price, stopLimitTimeInForce='GTC'))
		raise e
	d['_notional'] = Decimal(quantity) * Decimal(price)
	if renew:
		if side == 'SELL':
			cs = U.get_or_set(symbol + '.SELL.orders', [])
			cs.append(d)
			U.set(symbol + '.SELL.price', Decimal(price))
		if side == 'BUY':
			cs = U.get_or_set(symbol + '.BUY.orders', [])
			cs.append(d)
			U.set(symbol + '.BUY.price', Decimal(price))
	return d
create_order_oco=create_oco_order=create_oco_order_sell=create_sell_oco_order=create_spot_order_oco

def get_24hr_quoteVolume_dict(func=py.float):
	dsv={}
	for d in get_24hr_ticker(func=func):
		if d['bidPrice']>0:
			dsv[d['symbol']]=d['quoteVolume']
	return dsv

def get_24hr_ticker(symbol=None,func=py.float):
	fk=['priceChange','priceChangePercent','weightedAvgPrice','prevClosePrice','lastPrice','lastQty','bidPrice','bidQty','askPrice','askQty','openPrice','highPrice','lowPrice','volume','quoteVolume']
	if symbol:
		raise py.NotImp
	else:
		u='https://api.binance.com/api/v3/ticker/24hr'
	# ik=['openTime','closeTime','firstId','lastId','count']
		ds=N.HTTP.get_json(u,proxy='')		
		for d in ds:
			U.dict_convert_value(d,*fk,func=func)
		return ds

def get_exchange_info_by_name(*names,ss=None,client=None):
	''' available names:
['ss', 'dsdq', 'dsdt', 'dsd', 'dqbs', 'dbqs', 'dsbq', 'dsp', 'dbp', 'dqp', 'qs']	

dsdt=dsdq TRADING
dbp include BREAK [stop TRADING]
	'''
	client=get_client(client)
	# from decimal import Decimal,getcontext
	# getcontext().prec = 20 # 设置精度为足够大的值（例如20位）  # 没用  Decimal('0.00000001') 还是 Decimal('1E-8')

	if names:
		if py.len(names)==1 and ',' in names[0]:names=names[0].split(',')
	else:	
		names=('dbp','dqp')

	if not ss:
		ss=client.get_exchange_info()['symbols']
	dsdq={} # 历史所有交易对 dq 数据，【包括已经下架】
	dsdt={}
	dsd={}
	dqbs={}
	dbqs={}
	dbqt={}
	dsbq={}
	dqbt={}
	for d in ss:
		s=d['symbol']
		dsd[s]=d
		q=d['quoteAsset']
		b=d['baseAsset']
		dsbq[s]=(b,q)
		U.dict_add_value_list(dqbs,q,b)	
		U.dict_add_value_list(dbqs,b,q)	
		#assert d['quoteAssetPrecision']==8
		dq=U.dict_get_multi_keys_return_dict(d,'baseAsset','quoteAsset','status',)

		for df in d['filters']:
			#assert 'maxNumOrders': 200
			if df['filterType']=='LOT_SIZE':dq['stepSize']=df['stepSize'] # exclude MARKET_LOT_SIZE  'stepSize'
			for k in ['minNotional','tickSize',]:  # futures 'notional'
				if k in df:dq[k]=df[k]
			if  df['filterType']=='MIN_NOTIONAL':  # futures
				dq['minNotional']=df['notional']
			if  df['filterType']=='PERCENT_PRICE':  # futures
				dq['multiplierDown']=df['multiplierDown']
				dq['multiplierUp']  =df['multiplierUp']
		dsdq[s]=dq
		if d['status']=='TRADING':
			U.dict_convert_value(dq,'tickSize','stepSize','minNotional',func=lambda a:Decimal(a).normalize(),)
			dsdt[s]=dq

			U.dict_add_value_list(dbqt,b,q)	
			U.dict_add_value_list(dqbt,q,b)	

	dsp=get_all_price_dict(client)
	if 'USDTBVND' in dsp and not dsp['USDTBVND']:dsp['USDTBVND']=Decimal('0.000039') #越南盾 
 
	dbp={}
	dqp={}
	from decimal import Decimal as float
	for q in dqbs:
		if q=='USDT':
			dqp[q]=1
			continue

		s=q+'USDT'
		if s in dsp:
			dqp[q]=dsp[s]
			continue
		s='USDT'+q
		if s in dsp:
			if not dsp[s]:print('dsp[s]',s)
			dqp[q]=dqp['USDT']/dsp[s]
			continue

		if q in ['USDC','JPY']:
			dqp[q]=dsp['BTCUSDT'] / dsp['BTC'+q]
			continue

		# if q=='JPY':
		# 	dqp[q]=dsp['BTCUSDT'] / dsp['BTCUSDC']
		# 	continue
		print('unexcept:',q)

	dbp={'USDT':dqp['USDT']}
	for b,qs in dbqs.items():
		q='USDT'
		if q in qs and b+q in dsp:# future KeyError: 'DEFIUSDT'                          
			dbp[b]=dsp[b+q]*dqp[q]
		pass
	#print(U.diff(dbqs,dbp),U.len(dqbs,dbqs,dbp,))
	r=[]
	dlocals=py.locals()
	for sn in names:
		if '()' in sn:return eval(sn)
		if sn not in dlocals:raise py.ArgumentError(sn+' not found')
		r.append(dlocals[sn])
	if py.len(r)==1:
		return r[0]
	return r
	# return dbp,dqp
get_dbp_dqp=get_exchange_info_by_name

def get_trading_coin(client=None):
	client=get_client(client)
	ds=client.get_all_coins_info()
	return [d for d in ds if d['trading']]

def get_last_buy_price(symbol,client=None):
	client=get_client(client)
	symbol=spot_convert_symbol(symbol)
	ords=client.get_all_orders(symbol=symbol)
	# fords=client.get_my_trades(symbol=symbol)

	for d in ords[::-1]:
		if d['status']=='FILLED' and d['side']=='BUY':
			return Decimal(d['price'])
	return py.No('not found buy orders',symbol)


def get_account_balances(baseAsset='',client=None,):
	'''
if baseAsset:return [free,locked,free+locked]
else all	
	return {b:[free,locked,free+locked],....} '''
	client=get_client(client)
	balances= client.get_account()['balances']
	rd={}
	for d in balances:
		if d['free']==d['locked']=='0.00000000':continue
		if d['free']==d['locked']=='0.00':continue
		if d['free']==d['locked']=='0.0':continue
		free=Decimal(d['free'])
		locked=Decimal(d['locked'])
		rd[d['asset']]=[free,locked,free+locked]
	if baseAsset:
		assert baseAsset in rd
		return rd[baseAsset]
	return rd	
get_baseAsset_dict=get_spot_baseAsset_dict=get_account_balances


def get_spot_postion(dbp=None,return_dict=False,client=None,):
	client=get_client(client)
	if not dbp:
		dbp,dqp=get_exchange_info_by_name('dbp,dqp',client=client)

	balances= client.get_account()['balances']
	r=[]
	rd={}
	for d in balances:
		if d['free']==d['locked']=='0.00000000':continue
		if d['free']==d['locked']=='0.00':continue
		if d['free']==d['locked']=='0.0':continue
		
		if return_dict:rd[d['asset']]=d

		p=0
		if d['asset'] in dbp:
			p=dbp[d['asset']]
		elif d['asset'] in dqp:
			p=dqp[d['asset']]
		else:	
		# try:
		# except Exception as e:
			print('delist ',d)
			continue
		for k in ['free','locked']:
			n=d[k]=Decimal(d[k])
			d['u'+k[0]]=n*p
		d['all']=d['free']+d['locked']
		d['u']=d['uf']+d['ul']
		d['cp']=p
		for k in d:
			if not py.isinstance(d[k],Decimal):continue
			d[k]=d[k].normalize()# remove tail 0 
		
		r.append(d)
	if return_dict:return rd
	return r
get_postion_spot=get_spot_postion

def get_multi_intervals_kline(symbol,limit=22,intervals=B_intervals,spot=True):
	try:
		import async_get_kline
	except:
		sp='/home/qgb/4hq/bn/'
		if not F.exists(sp):sp='/home/qgb/bn/'
		async_get_kline=U.import_from_file(sp+'async_get_kline.py')

	return async_get_kline.sync(symbol=symbol,limit=limit,intervals=intervals,spot=spot)

mkline=get_multi_intervals_kline

def get_min_exclude_first(first,symbol='HOOKUSDT',end=None,intervals=g5intervals,client=None):
	''' ,start='2016-01-01'
first is datetime or str	
	'''
	import pandas
	# symbol,min_p,min_t,min_qv, max_p,max_t,max_qv,rate,(min_row,max_row)=get_min_max_price_and_time(symbol)
	# if min_t!=first:
	# 	return symbol,min_p,min_t,min_qv, max_p,max_t,max_qv,rate
	# for interval in intervals:
	if py.isint(first):
		first=pandas.Timestamp(first,unit='ms').tz_localize('UTC').tz_convert('Asia/Shanghai')

	ct=pandas.Timestamp(U.itime_ms(),unit='ms').tz_localize('UTC').tz_convert('Asia/Shanghai')

	start_M=first.replace(day=1,hour=8,minute=0,second=0,microsecond=0)
	if first.year!=ct.year or first.month!=ct.month:
		Ms=get_klines(symbol=symbol,start=start_M,end=None,interval='1M')
		M1=Ms.sort_values('Low').iloc[1]
		M1p=M1['Low']
		end_M=Ms.iloc[0]['CloseTime']
		start_M=M1['OpenTime']
	else:
		M1p=0
		end_M=None

	start_d=first.replace(hour=8,minute=0,second=0,microsecond=0)
	if first.year!=ct.year or first.month!=ct.month or first.day!=ct.day:
		ds=get_klines(symbol=symbol,start=start_d,end=end_M,interval='1d')
		d1=ds.sort_values('Low').iloc[1]
		d1p=d1['Low']
		end_d=ds.iloc[0]['CloseTime']
		if not end_M:
			M1p=d1p
			end_M=end_d
			start_M=d1['OpenTime']
	else:
		d1p=0
		end_d=None
	
	if M1p<=d1p:
		if first.year!=ct.year or first.month!=ct.month or first.day!=ct.day or first.hour!=ct.hour:
			hs=get_klines(symbol=symbol,start=first.replace(minute=0,second=0,microsecond=0),end=end_d,interval='1h')
			h1=hs.sort_values('Low').iloc[1]
			h1p=h1['Low']
			end_h=ds.iloc[0]['CloseTime']
			if not end_M:
				M1p=h1p
				end_M=end_h
		else:
			h1p=0
			end_h=None

		if M1p<h1p:
			ms=get_klines(symbol=symbol,start=first.replace(second=0,microsecond=0),end=end_h,interval='1m')
			m1=ms.sort_values('Low').iloc[1]
			m1p=m1['Low']
			end_m=ms.iloc[0]['CloseTime']
			
			if M1p<m1p:
				ss=get_klines(symbol=symbol,start=first,end=end_m,interval='1s')
				s1=ss.sort_values('Low').iloc[1]
			if M1p<s1['Low']:

				return get_min_max_price_and_time(symbol,client=client,start=start_M)

	return
# 	U.time_delta

def try_get_kline_1s(symbol,start,end=None,end_err=None,asecs=50*20+5,client=None):
	import pandas as pd
	client=get_client(client)
	symbol=spot_convert_symbol(symbol)
	if py.istr(start):
		if '+' not in start:
			start+='+00:00'
		start=U.utc(start,return_str=0)
	elif py.getattr(start,'astimezone',0):
		start=start.astimezone(0)
	if not end:
		end=start+gtimedelta_second*asecs
	for n in range(asecs):
		try:	
			klines=client.get_historical_klines(symbol,interval='1s',start_str=start.strftime("%Y-%m-%d %H:%M:%S"),
				end_str=(end-gtimedelta_second*n).strftime("%Y-%m-%d %H:%M:%S"))
			return get_klines(klines=klines)
		except TypeError as e:
			# return start,end
			# td=end-start
			# return try_get_kline_1s(symbol=symbol,start=start,end=end-(td/2),end_err=end)
			continue
	return klines
get_klines_1s=try_get_kline_1s

def get_min_max_price_and_time(symbol,client=None,start='2017-01-01',end=None,intervals=None):
	'''
return symbol,min_p,min_t,min_qv, max_p,max_t,max_qv,rate
	'''
	symbol=spot_convert_symbol(symbol)
	min=get_price_and_time(symbol=symbol,client=client,start=start,end=end,return_list=True,intervals=intervals)
	if not min:return min
	min=min[-1]
	t=min['OpenTime']
	# if t.minute==t.second==0:
	# 	m2=get_klines(symbol,interval='1m',limit=2,client=client)
	# 	return py.No('t.minute==t.second==0',min,m2)

	row=[symbol,min['Low'],min['OpenTime'],min['QuoteAssetVolume'] ,]

	ms=get_price_and_time(symbol=symbol,client=client,start=min['OpenTime'].tz_convert('UTC').strftime('%Y-%m-%d %H:%M:%S'),end=end,return_list=return_list,condition=lambda mdata:mdata['High'].idxmax())
	max=ms[-1]
	rate=(max['High']-min['Low'])/min['Low']
	row.extend([max['High'],max['OpenTime'],max['QuoteAssetVolume'], rate ,U.obj_repr((min,max),repr='min,max=_[-1] #pandas obj_repr')])
	#obj_repr 不能用[]  ,  只能用tuple
	return row
get_min_max=get_min_max_price=get_min_max_and_time=get_min_max_price_and_time


def get_max_price_and_time(symbol,client=None,start='2017-01-01',end=None,return_list=True):
	# client=get_client(client)
	return get_price_and_time(symbol=symbol,client=client,start=start,end=end,return_list=return_list,condition=lambda mdata:mdata['High'].idxmax())

def get_price_and_time(symbol,client=None,start='2017-01-01',end=None,return_list=True,condition=lambda mdata:mdata['Low'].idxmin(),
			   intervals=g5intervals):
	client=get_client(client)
	symbol=spot_convert_symbol(symbol)
	if not intervals:intervals=('1M','1d','1h','1m','1s')
	rs=[]
	qa=0
	for interval in intervals:
		data=get_klines(symbol=symbol,interval=interval,start=start,end=end,client=client)
		# if interval=='1M':
		# 	qa=data['QuoteAssetVolume'].sum()/10**8
		# 	mdata=data.loc[data.index!=0]
		# else:
		# 	mdata=data	
		# return data
		# return data.loc[data['Low'] == data['Low'].min()]
		# row=data.loc[data.index==data.loc[data.index!=0]['Low'].idxmin() ] # pandas.core.frame.DataFrame
		if data.empty:continue


		row=data.iloc[condition(data)] # pandas.core.series.Series
		start=row['OpenTime'].tz_convert('UTC').strftime('%Y-%m-%d %H:%M:%S')
		end=row['CloseTime'].tz_convert('UTC').strftime('%Y-%m-%d %H:%M:%S')


		rs.append(row)
	if return_list:return rs	
	else:
		return [row.Low,
	  row['OpenTime'].tz_localize('UTC').tz_convert('Asia/Shanghai').strftime('%Y-%m-%d %H:%M:%S'),
	  py.round(qa,3),]
get_min_price_and_time=get_price_and_time

def get_all_price_dict(client=None):
	client=get_client(client)
	# aps=
	rd={}
	for d in client.get_all_tickers(): # {'symbol': 'ETHBTC', 'price': '0.05247000'}
		if d['symbol'] in rd:
			raise AssertionError(d)
		rd[d['symbol']]=Decimal(d['price'])
	return rd


def renew_sell_spot_order(symbol, price, quantity=None, last_order=None, more=0, client=None, 
                    time=True, create_if_not_exists=False):
    """带创建保障的卖单更新函数"""
    client = get_client(client)
    symbol = spot_convert_symbol(symbol)
    
    # 获取订单记录队列
    cs = U.get_or_set(symbol+'.SELL.orders', collections.deque([], maxlen=99))
    xs = U.get_or_set(symbol+'.SELL.xs', collections.deque([], maxlen=99))
    
    # 订单ID处理逻辑
    if not last_order:
        last_order = get_open_orders(side='SELL', symbol=symbol, return_dict=1).get(symbol, {}).get('orderId')
    
    if last_order:
        try:
            # 尝试取消旧订单
            x = client.cancel_order(symbol=symbol, orderId=last_order)
            xs.append(x)
        except Exception as e:
            if create_if_not_exists:
                print(f"{e} 订单{last_order}不存在，执行创建逻辑")
            else:
                raise e
    
    # 数量计算逻辑
    quantity = quantity or get_min_order_quantity(symbol, price=price, more=more)
    price = round_price_quantity(symbol, price=price)
    
    # 订单创建逻辑
    try:
        c = client.create_order(
            symbol=symbol, side='SELL', type='LIMIT',
            timeInForce='GTC', quantity=quantity, price=price
        )
        cs.append(c)
    except Exception as e:
        if cs and create_if_not_exists:
            print("使用历史订单数据重建")
            d = cs[-1]
            return create_spot_order_limit_price(
                symbol=d['symbol'], price=d['price'],
                quantity=d['origQty'], renew=True, side='SELL', client=client
            )
        raise e
    U.set(symbol+'.SELL.price', Decimal(price))
    return c
renew_sell_order=renew_sell_spot_order

def renew_buy_order(symbol,price,quantity=None,last_order=None,more=0.05,client=None,time=True,create_if_not_exist=False,debug=False):
	client=get_client(client)
	symbol=spot_convert_symbol(symbol)
	cs=U.get_or_set(symbol+'.BUY.orders',[])
	xs=U.get_or_set(symbol+'.xs',[])

	if last_order:
		if py.isdict(last_order):
			if ('workingTime' in last_order) and (last_order not in cs):
				cs.append(last_order)
			last_order=last_order['orderId']
	else:
		os=get_open_orders(side='BUY',symbol=symbol,return_dict=1)
		if os:
			last_order=os[symbol]['orderId']
		# else:

	# print('renew_buy_order',last_order)
	if not py.isint(last_order) or last_order<1:
		if cs:last_order=cs[-1]['orderId']
		
	# try:
	if create_if_not_exist:
		try:
			x=client.cancel_order(symbol=symbol,orderId=last_order)
			xs.append(x)
		except Exception as e:
			print(e)
			# return futures_create_short_order_limit_price(symbol=symbol,price=price,limit_notional=limit_notional,renew=True)	
	else:
		x=client.cancel_order(symbol=symbol,orderId=last_order)
		xs.append(x)
	# except Exception as e:
	# 	print(U.stime(),'cancel_order',e)	

	if not quantity:
		quantity=get_min_order_quantity(symbol,price=price,more=more)
	# if py.isinstance(price,Decimal):
	price=round_price_quantity(symbol,price=price)
	if debug:return U.v.client.create_order(symbol=symbol,side='BUY',type='LIMIT',timeInForce='GTC',quantity=quantity,price=price,)
	try:	
		d=client.create_order(symbol=symbol,side='BUY',type='LIMIT',timeInForce='GTC',quantity=quantity,price=price,)
		d['_notional']=Decimal(d['origQty'])*Decimal(d['price'])
		cs.append(d)
	except Exception as e:
		print('renew_buy_order',e)
		d=cs[-1]
		if d['orderId']==last_order:
			create_spot_order_limit_price(symbol=d['symbol'],price=d['price'],quantity=d['origQty'],renew=True,side='BUY',client=client)
			# client.create_order(symbol=d['symbol'],side='BUY',type='LIMIT',timeInForce='GTC',quantity=d['origQty'],price=d['price'],)
		raise e	
	U.set(symbol+'.BUY.price',Decimal(price))
	return d
renew_order=renew_buy_order


def get_open_orders(side='BUY',symbol=None,client=None,price=True,time=True,sort=2,return_dict=False):
	'''
return [ [symbol,_cp,_rate,order_price,order_origQty,_notional,stime,orderId],]
	
# if o['time']!=o['updateTime']:raise AssertionError(o)
AssertionError: {'symbol': 'AERGOBUSD', 'orderId': 104317914, 'orderListId': 91310910, 'clientOrderId': 'and_3d5f410d721c46e3a023aebbcff33540', 
'price': '0.09280000', 'origQty': '114.00000000', 'executedQty': '0.00000000', 'cummulativeQuoteQty': '0.00000000', 'status': 'NEW', 
'timeInForce': 'GTC', 'type': 'STOP_LOSS_LIMIT', 'side': 'SELL', 'stopPrice': '0.09180000', 'icebergQty': '0.00000000', 
'time': 1692244682827, 'updateTime': 1692308284014, 'isWorking': True, 'workingTime': 1692308284014, 'origQuoteOrderQty': '0.00000000', 
'selfTradePreventionMode': 'NONE'}



	'''

	client=get_client(client)
	from datetime import datetime   
	dsps={}
	dsl={}
	for o in client.get_open_orders(symbol=symbol):
		if o['side']==side:
			p=Decimal(o['price']).normalize()
			q=Decimal(o['origQty']).normalize()
			if 'E+' in py.str(q):
				q=Decimal(U.float_to_str(q))

			pq=(p*q).normalize()
			U.dict_value_add_list(dsps,o['symbol'],(p,q,pq,U.stime(o['time']),o['orderId'],o)  )
		# if time:
			
			# dsl[o['symbol']]=[ U.IntRepr(o['time'],repr=U.stime(o['time'])) ]
			# dsl[o['symbol']]=[ datetime.fromtimestamp(o['time']/1000) ]

			# U.dict_value_add_list(dsl,o['symbol'],U.stime(o['time']),)
			# dsl[o['symbol']]=[ U.stime(o['time']) ]
	if price:		
		dsp=get_all_price_dict(client)
	rbos=[]
	dso={}
	for s,ps in dsps.items():
		assert ps
		ps=py.sorted(ps,key=lambda x:x[0])  # small to big
		row=[s]
		if side=='BUY':ip=-1
		if side=='SELL':ip=0
		if price:
			mp=ps[ip][0] # BUY max(ps)  , SELL min(ps)  ,[0] is price
			cp=Decimal(dsp[s])
			row.extend([cp,(cp-mp)/mp,])
			# ps[-1][-1]['_row']=row  #  o == ps[-1][-1]
			ps[ip][-1]['_cp']=cp
			ps[ip][-1]['_rate']=(cp-mp)/mp
			ps[ip][-1]['_notional']=ps[-1][2]

		row.extend(ps[ip][:-1])  # len(ps),  左闭右开 exclude o
		# row.extend(dsl.get(s,[]))
		if return_dict:
			dso[s]=ps[ip][-1]
		else:	
			rbos.append(row)

	if return_dict:
		return dso
	if sort and py.isint(sort):
		rbos.sort(key=lambda x:x[2])	
	return rbos
buy_orders=get_buy_orders=open_orders=get_open_orders

def get_sell_orders(symbol=None,client=None,price=True,time=True,sort=2,return_dict=False):
	return get_open_orders(side='SELL',symbol=symbol,client=client,price=price,time=time,sort=sort,return_dict=return_dict)
sell_orders=get_sell_orders

def get_klines(symbol='BTCUSDT',start=None,end=None,interval='1d',klines=None,limit=1000,print_time=False,client=None,**ka):
	''' 
如果start=None ，则返回从现在算起 最近 limit 条 数据
	'''
	start=U.get_duplicated_kargs(ka,'start_str',default=start)
	end=U.get_duplicated_kargs(ka,'end_str',default=end)
	if print_time:print(U.stime())
	if not klines:
		client=get_client(client)
		if py.getattr(start,'isoformat',0):
			start=start.astimezone(0).isoformat()
		if py.getattr(end,'isoformat',0):
			end=end.astimezone(0).isoformat()
		klines=client.get_historical_klines(symbol,interval,start_str=start,end_str=end,limit=limit)
	if print_time:print(U.stime())
	import pandas #as pd
	columns=[
		'OpenTime',
		'Open',
		'High',
		'Low',
		'Close',
		'Volume',
		'CloseTime',
		'QuoteAssetVolume',
		'NumberofTrades',
		'TakerBuyBaseAssetVolume',
		'TakerBuyQuoteAssetVolume',
		'Ignore']
	if py.istr(klines):
		data=pandas.read_json(klines)
		data.columns=columns
	else:	
		data = pandas.DataFrame(klines, columns=columns)
	
	data=data.astype(dtype={
 'Open'  :float, 
 'High'  :float, 
 'Low'   :float, 
 'Close' :float, 
 'Volume':float, # 量
 'QuoteAssetVolume':float, # 额
})




	# cols =   
	# 批量转换时区
	for C in ['OpenTime', 'CloseTime']:
		data[C]=pandas.to_datetime(data[C],unit='ms')
		data[C] = data[C].apply(lambda x: x.tz_localize('UTC').tz_convert('Asia/Shanghai'))
	if print_time:print(U.stime())
	# data['CloseTime']=pandas.to_datetime(data['CloseTime'],unit='ms')
	return data
get_historical_klines=get_klines

def get_min_price_row(*a,data=None,**ka):
	if not data:
		data=get_klines(*a,**ka)
	# return data.loc[data['Low'] == data['Low'].min()]
	return data.loc[data['Low'] == data['Low'].min()]
get_min_price=get_min_price_row

def get_min_max_and_time_from_data(data):
	rn=data.loc[data['Low'] == data['Low'].min()]
	rx=data.loc[data['High'] == data['High'].max()]

	tn=rn['OpenTime'].dt.strftime('%Y-%m-%d').iloc[0]
	tx=rx['OpenTime'].dt.strftime('%Y-%m-%d').iloc[0]
	# if data.empty:return

	return (
Decimal(str(rn['Low'].values[0])),tn,Decimal(str(rn['QuoteAssetVolume'].values[0])),
Decimal(str(rx['High'].values[0])),tx,Decimal(str(rx['QuoteAssetVolume'].values[0]))
	)

def spot_convert_symbol(s,):
	s0=s
	if s.islower():
		# if not s.endswith('usdt'):
		s=(s).upper()
	if s.isupper():
		if s.endswith('TRY'):pass
		elif not s.endswith('USDT'):
			s+='USDT'
		else:
			if py.len(s)>4:return s #处理 BREAK 状态 symbol 	
	if s in U.get_or_dill_load(gs_dsdt):
		return s
	else:
		raise py.ArgumentError(s+' not found in gs_dsdt',s0,s)
	# create_future_order
get_spot_symbol=spot_symbol=spot_get_symbol=spot_get_symbol=spot_convert_symbol

################# futures 
def futures_convert_symbol(s):
	s0=s
	if s.islower():
		if not s.endswith('usdt'):
			s=(s).upper()
	if s.isupper():
		if not s.endswith('USDT'):
			s+='USDT'
	if s in U.get_or_dill_load(gs_fdsdt):
		return s
	else:
		raise py.ArgumentError(s+' not found in gs_fdsdt',s0,s)
	# create_future_order
get_futures_symbol=futures_symbol=futures_get_symbol=futures_get_symbol=futures_convert_symbol


def futures_get_symbol_price(symbol,client=None):
	'''    {'symbol': 'BTCUSDT', 'price': '44688.50', 'time': 1707391955017}    '''
	import urllib,json
	urp = urllib.request.urlopen(f'https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}')

	# 解析 JSON 数据
	data=urp.read().decode("utf-8")
	j=json.loads(data)
	return Decimal(j['price'])
futures_get_price=get_price_futures=get_symbol_price_futures=futures_get_symbol_price

def get_symbol_price(symbol,client=None):
	client=get_client(client)
	Decimal(client.get_symbol_ticker(symbol=symbol)['price'])
get_symbol_ticker=get_symbol_price

def futures_all_price_dict(client=None):
	client=get_client(client)
	rd={}
	for d in client.futures_mark_price():
		rd[d['symbol']]=d
	return rd
futures_mark_price=futures_all_price_dict

def get_price_upper_rate(price,low,ndigits=4):
	# return round(Decimal(price) / (Decimal(price)-Decimal(low) ),ndigits)
	return round( (Decimal(price)-Decimal(low))/Decimal(low),ndigits)

def futures_get_open_orders_SELL_SHORT(current_price=True,return_dict=False,client=None,):
	''' short_orders  '''
	client=get_client(client)
	r=[]
	dso={}

	if current_price:dsd=futures_all_price_dict(client=client)

	for d in client.futures_get_open_orders():
		if not (d['status']=='NEW' and d['side']=='SELL' and d['positionSide']=='SHORT'):continue
		
		if current_price:
			dp=dsd[d['symbol']]
			
			dp['price']=d.pop('price')
			dp['symbol']=d.pop('symbol')
			for k in ['markPrice','indexPrice','estimatedSettlePrice',]:
				dp[k]=dp.pop(k)
				dp[k+'_rate']=get_price_upper_rate(dp['price'],dp[k])
			d.update(dp)
		if return_dict:dso[d['symbol']]=d

		r.append(d)
	if return_dict:return dso	
	return r
futures_get_all_order=futures_get_all_orders=sell_short_orders=get_open_orders_SELL_SHORT=futures_get_open_orders_SELL_SHORT

def get_future_symbol_dict(client=None):
	client=get_client(client)
	rd={}
	for d in client.futures_exchange_info()['symbols']:
		rd[d['symbol']]=d
	return rd	

def get_all_future_open_orders(symbol='',client=None,float=py.float,side=None,positionSide=None,return_cp=True,return_list=False):
	import pandas
	client=get_client(client)
	r=[]
	# client.futures_ticker(symbol=s)
	if return_cp:
		dsp={d['symbol']:Decimal(d['price']) for d in client.session.get("https://fapi.binance.com/fapi/v2/ticker/price").json()}

	for d in client.futures_get_open_orders(symbol=symbol):
		if d['status']=='NEW': # and d['side']=='SELL' and d['positionSide']=='SHORT' 的反面
			# if side=='SELL':
			if side and d['side']!=side:continue
			
			if positionSide and d['positionSide']!=positionSide:continue
			# if side=='BUY':
			# 	if d['side']!='BUY':continue #  or d['positionSide']!='SHORT'

			s=d['symbol']
			op=Decimal(d['price'])
			if return_cp:
				cp=dsp[s]
				rate=(op-cp)/cp
				d['cp']=cp
				d['rate']=rate
				d['op']=op
			# d['rate']=py.round(rate,5)

			qty=Decimal(d['origQty'])
			d['notional']=py.round(qty*op,3)
			r.append(d)
	if not r:return r
	if return_list:return r			
	# print(len(r))	
	df = pandas.DataFrame(r)
	for C in ['time','updateTime']:
		df[C]=pandas.to_datetime(df[C],unit='ms')
		df[C] = df[C].apply(lambda x: x.tz_localize('UTC').tz_convert('Asia/Shanghai'))

	cs=py.list(df.columns)
	if return_cp:hcs=['symbol','rate','cp','price','notional','origQty',]
	else        :hcs=['symbol','price','notional','origQty',]
	cs=U.list_reindex_by_value(cs,*hcs)
	cs=U.list_reindex_to_tail(cs,'time','updateTime','orderId','side','positionSide',)
	df = df.reindex(columns=cs)
	return df
get_future_open_orders=futures_get_open_orders=get_future_all_open_orders=get_all_future_open_orders

def get_all_future_short_open_orders(client=None,float=py.float,return_list=False):
	'''
	 client.futures_ticker(symbol="BTCUSDT")	
{'symbol': 'BTCUSDT',
 'priceChange': '1018.30',
 'priceChangePercent': '3.763',
 'weightedAvgPrice': '27611.63',
 'lastPrice': '28077.20',
 'lastQty': '0.016',
 'openPrice': '27058.90',
 'highPrice': '28365.20',
 'lowPrice': '27015.00',
 'volume': '306582.521',
 'quoteVolume': '8465242356.00',
 'openTime': 1696138200000,  # 一分钟级别
 'closeTime': 1696224650629, # 当前时间  0....59
 'firstId': 4130912653,
 'lastId': 4133819087,
 'count': 2896909}
	'''
	return get_all_future_open_orders(client=client,float=float,positionSide='SHORT',return_list=return_list,) #,side='SELL'
get_all_future_open_orders_short=get_all_future_short_open_orders

def get_future_minQty_tickSize(symbol,client=None,float=py.float):
	# ,dsd=None
	# if not dsd:
	# 	dsd=U.get_or_set('get_future_symbol_dict',lazy_default=lambda:get_future_symbol_dict(client=client) )
	d=U.get_or_dill_load(gs_fdsdt)[symbol]	
	return d['stepSize'],d['tickSize']

	mqs=[]	
	tickSize=1
	for d in dsd[symbol]['filters']:
		if 'tickSize' in d:
			tickSize=float(d['tickSize'])

		if 'minQty' in d:
			if not mqs:mqs.append(d['minQty'])
			elif d['minQty'] in mqs:
				# assert 
				continue
			else:
				print(symbol,d)
				raise EnvironmentError('duplicate minQty',symbol,d)
	return float(mqs[0]),tickSize
get_future_qty_tickSize=get_future_min_qty_tickSize=get_future_minQty_tickSize

gfuture_zero_positionAmt=('0', '0.0', '0.000', '0.00')

def futures_get_short_postion(symbol=None,client=None,):
	client=get_client(client)

	def get_n(d):
		mq,mt=get_future_minQty_tickSize(d['symbol'],client=client,float=Decimal)
		n=Decimal(d['positionAmt'])/mq
		assert n==py.int(n)
		return py.abs(py.int(n))
		if symbol:
			return symbol==d['symbol']
		else:
			return True
	# ds=	[d 
	r={}
	for d in client.futures_position_information():
		if d['positionAmt'] in gfuture_zero_positionAmt:continue
		if symbol:
			if symbol==d['symbol']:
				return get_n(d)
		else:	
			r[d['symbol']]=get_n(d)
	if symbol:raise py.ArgumentError(symbol,'Not found !!')		
	return r	
get_future_short_postion=futures_get_short_postion

def futures_get_finish_orders_SELL_SHORT(symbol,client=None):
	client=get_client(client)

def futures_finish_short_order_oco(symbol,price,quantity=0,client=None,debug=False):
	client=get_client(client)
	
	
def futures_finish_short_order_limit_price(symbol,price,quantity=0,client=None,debug=False):
	client=get_client(client)
	symbol=futures_convert_symbol(symbol)
	if not quantity:
		# quantity=futures_get_min_order_quantity(symbol=symbol,price=price)
		quantity=U.get_or_dill_load(gs_fdsdt)[symbol]['stepSize']

	price,quantity=futures_round_price_quantity(symbol,price=price,quantity=quantity)		

	params = {
		"symbol": symbol,             # 交易对
		"side": "BUY",               # 买入BUY平空,SELL 开空

		"price": price,          # x价格
	#    "stopPrice": 1884,           # 触发价格必须比现价高,否则 APIError(code=-2021): Order would immediately trigger.(并不会实际成交)
		"type": 'LIMIT',# binance.enums.FUTURE_ORDER_TYPE_LIMIT,
		'quantity':quantity,
		'timeInForce':'GTC',
	}
	if gdualSidePosition:params["positionSide"]="SHORT"    # 双向持仓模式 空仓方向
	else:
		params["positionSide"]="BOTH" # 单向持仓模式 这样才能平仓
		params["reduceOnly"]=True     # 单向持仓模式 这样才能平仓
	if debug:return params
	try:
		rf=client.futures_create_order(**params)
		return rf
	except Exception as e:
		print(U.v.client.futures_create_order(**params),' #',e)
		return py.No(e)
	
finish_futures_order_limit_price=futures_finish_short_order_limit_price

def futures_create_short_order_limit_price(symbol,price,quantity=0,renew=True,limit_notional=None,client=None,debug=False):
	client=get_client(client)
	symbol=futures_convert_symbol(symbol)
	price=futures_round_price_quantity(symbol,price=price)
	if not quantity:
		quantity=futures_get_min_order_quantity(symbol=symbol,price=price,limit_notional=limit_notional)
	price,quantity=futures_round_price_quantity(symbol,price=price,quantity=quantity)	
	params = {
		"symbol": symbol,             # 交易对
		"side": "SELL",               # 买入BUY平空,SELL 开空
		"price": price,          # x价格
	#    "stopPrice": 1884,           # 触发价格必须比现价高,否则 APIError(code=-2021): Order would immediately trigger.(并不会实际成交)
		"type": 'LIMIT',# binance.enums.FUTURE_ORDER_TYPE_LIMIT,
		'quantity':quantity,
		'timeInForce':'GTC',
		#'reduceOnly':True,
	}
	if gdualSidePosition:params["positionSide"]="SHORT"    # 双向持仓模式 空仓方向
	


	if debug:return U.v.client.futures_create_order(**params)
	d=client.futures_create_order(**params)
	d['_notional']=Decimal(d['origQty'])*Decimal(d['price'])
	if renew:
		cs=U.get_or_set(symbol+'.short.orders',[])
		cs.append(d)
	return d

make_future_order=create_future_order=create_future_order_limit_price=futures_create_short_order_limit_price

def futures_cancel_order(symbol,orderId=None,client=None):
	client=get_client(client)
	if py.isdict(symbol):
		orderId=symbol['orderId']
		symbol=symbol['symbol']
	symbol=futures_convert_symbol(symbol)
	if not orderId:
		os=get_all_future_open_orders(symbol,return_cp=0,return_list=1)
		assert os
		orderId=os[0]['orderId']

	return client.futures_cancel_order(symbol=symbol,orderId=orderId)
cancel_future_order=cancel_futures_order=futures_cancel_order


def cancel_all_future_order(side=None,exclude_symbols=('ETHUSDT',),client=None):
	client=get_client(client)
	ords=client.futures_get_open_orders()
	r=[]
	for n,d in enumerate(ords):
		s=d['symbol']
		if side and d['side']!=side:continue
		if exclude_symbols and s in exclude_symbols:continue
		try:
			rd=futures_cancel_order(d,client=client)
		except Exception as e:
			rd=e	

		r.append([n,d,rd])

	return r	

import collections

BOLL2 = collections.namedtuple('Data', ['t', 'cp', 's_1', 'ru2', 'u2', 'm2', 'l2', 'rl2',
					's_2', 'ru1', 'u1', 'm1', 'l1', 'rl1'])

def bollinger_bands_up_values(*a,**ka):
	index=U.get_duplicated_kargs(ka,'index','col_index',default=-4)
	r=bollinger_bands(*a,**ka)
	vs=[]
	if py.islist(r):
		for row in r:
			vs.append(row[index])
	if py.isdict(r):
		for t in r:
			vs.append([t,py.getattr(r[t],BOLL2._fields[index])])
	return vs
boll_v=boll_value=boll_up=boll_up_value=bollinger_bands_up_values

def bollinger_bands(symbol,cs=B_intervals_future,limit=30,client=None,return_dict=False,decs=0):
	# import ta.volatility
	import talib,numpy,numpy as np
	client=get_client(client)
# client.futures_klines(symbol="ETHUSDT", interval='1w',limit=30)
	if py.isdict(symbol):
		decs=symbol['pricePrecision']
		symbol=symbol['symbol']
	else:
		# decs=2
		pass
	r=[]
	for interval in cs:
		ks=client.futures_klines(symbol=symbol, interval=interval,limit=limit)
		fcs=numpy.array([float(i[4]) for i in ks])
		# ma21 = talib.MA(fcs, timeperiod=21)
		# numpy.trunc(ma21*10**decs)/(10**decs)
		up,mid,low= talib.BBANDS(fcs, 
									 nbdevup=3,
									 nbdevdn=3,
									 timeperiod=21)
		if decs:
			up=numpy.trunc(up*10**decs)/(10**decs)
			mid=numpy.trunc(mid*10**decs)/(10**decs)
			low=numpy.trunc(low*10**decs)/(10**decs)

		c=fcs[-1]
		# if interval!='1M':
		# 	c=U.IntRepr(c,repr='')
		s=U.StrRepr('\t')
		r.append([U.StrRepr(interval,size=3),c,
			s,
			(up[-2]-c)/c, up[-2],mid[-2],low[-2], (c-low[-2])/c,
			s,
			(up[-1]-c)/c, up[-1],mid[-1],low[-1], (c-low[-1])/c,
			
			])
	rd={}	
	if return_dict:
		for row in r:
			t=BOLL2(*row)
			rd[t.t]=t
		return rd	
	return r	
boll=bollinger_bands

gdpurls_notify={
'socks5h://127.7.7.7:31080':['http://192.168.1.16:1122/','http://192.168.1.5:1133/',],
'socks5://127.7.7.7:31080':['http://192.168.1.3:1122/','http://192.168.1.5:1122/','http://192.168.1.16:1122/','http://192.168.1.20:1133/'],
'socks5://127.7.7.7:11230':['http://127.0.0.1:1122/',],
	}
def set_gdpurls_notify(name,base):
	if name in ['x230',230]:name='http://192.168.1.16:1122/'
	if name in ['lenovo',3]:name='http://192.168.1.3:1122/'
	if py.isint(base):base=f'http://192.168.1.{base}:1122/'
	d={}
	for proxy,urls in gdpurls_notify.items():
		us=[]
		for u in urls:
			if u==name:u=base
			us.append(u)
		d[proxy]=us
	return U.set('B.notify.dpurls',d)
set_notify_urls=set_gdpurls_notify

def non_blocking_notify(s,max_vol=17,print_req=1):
	dpurls=U.get_or_set('B.notify.dpurls',gdpurls_notify)

	if not max_vol:return py.No(s,max_vol)
	for proxy,urls in dpurls.items():
		if max_vol>66 and proxy=='socks5h://127.7.7.7:31080':continue
		f=lambda :N.HTTP.get(f"""{urls[0]}r=U.tts(r'''{s}''',v=U.get_or_set({max_vol},{max_vol}),ms={U.itime_ms()},)""",
			print_req=print_req,proxies=proxy,headers=None)
		U.thread(target=f).start()	

	
	if max_vol>66:
		for proxy,urls in dpurls.items():
			if len(urls)<=1:continue
			for url in urls[1:]:
				f=lambda :N.HTTP.get(f"""{url}r=U.tts(r'''{s}''',v=U.get_or_set({max_vol},{max_vol}),ms={U.itime_ms()},)""",
					print_req=print_req,proxies=proxy,headers=None)
				U.thread(target=f).start()	

		# f=lambda :N.HTTP.get(f"""http://192.168.1.16:1122/r=U.tts(r'''{s}''',v=U.get_or_set({max_vol},{max_vol}),ms={U.itime_ms()},)""",
		# 	print_req=1,proxies='socks5://127.7.7.7:31080')
		# U.thread(target=f).start()	

		# f=lambda :N.HTTP.get(f"""http://192.168.1.20:1133/r=U.tts(r'''{s}''',v=U.get_or_set({max_vol},{max_vol}),ms={U.itime_ms()},)""",
		# 	print_req=1,proxies='socks5://127.7.7.7:31080')
		# U.thread(target=f).start()	


	return s,max_vol	
notify=non_blocking_notify

gdshl=U.get_or_set('gdshl',{})
# def 
gdnds=U.get_or_set('gdnds',{})
gdnc=U.get_or_set('gdnc',{})
def process_symbol_dict(ds):
	'''
2023-07-07__00.15.51__.136 $$$ NEARUSDT $$$: 
{'e': 'trade', 'E': 1688660151070, 's': 'NEARUSDT', 't': 128351667, 'p': '1.33100000', 'q': '36.00000000', 'b': 1981145382, 'a': 1981145107, 'T': 1688660151069, 'm': False, 'M': True}

2023-07-07__00.15.51__.136 $$$ NEARUSDT $$$: 
{'e': 'trade', 'E': 1688660151070, 's': 'NEARUSDT', 't': 128351668, 'p': '1.33100000', 'q': '112.70000000', 'b': 1981145382, 'a': 1981145150, 'T': 1688660151069, 'm': False, 'M': True}	
	'''
	n=len(ds)
	U.dict_key_count(gdnc,n)
	if n<130 or n>1000:
		gdnds[n]=ds

	for d in ds:
		s=d['s']
		# if 'AERGO' not in s:
		# 	continue
		# s=d['s']

		if s in gdshl:
			for k in 'abchlowx':
				v=Decimal(d[k])
				if v>gdshl[s][k+'h']:gdshl[s][k+'h']=v
				if v<gdshl[s][k+'l']:gdshl[s][k+'l']=v
			gdshl[s]['n']+=1
		else:
			gdshl[s]={'n':1}
			for k in 'abchlowx':
				v=Decimal(d[k])
				gdshl[s][k+'h']=gdshl[s][k+'l']=v
			# print(d)
	return ds

def process_msg_dict(d,user=''):
	''' user  现货 '''
	msg=''
	if 'o' in d and py.isdict(d['o']):
		s=d['o']['s']
		t=d['o']['T']
		p=d['o']['p']
	elif 'X' in d and d['X']=='FILLED':
		s=d['s']
		t=d['T']
		p=d['p']
	else:return	

	if d['S']=='BUY':side='买入'
	if d['S']=='SELL':side='卖出'

	msg=f'''B {user}账号 {T.space.join(s)} 现货价格 {p} {side}! {U.zh_time(t)}__{U.itime_ms()%(10000)}__t {user}''' #10 s
	notify(msg)

	N.post_with_new_thread(f"http://127.0.0.1:1144/r=U.dict_pop(B.gdsrpc,'{s}')",b'')
	# if s in N.rpc_get(base='http://127.0.0.1:1144/',varname='B.gdsrpc'):
	# 	N.get('http://127.0.0.1:1144/B.gdsrpc.clear()',proxy='')


	return 2

def process_future_msg_dict(d,user=''):
	''' 
{'e': 'ORDER_TRADE_UPDATE', 'T': 1744647768318, 'E': 1744647768319, 'o': {'s': 'BABYUSDT', 'c': 'x-Cb7ytekJbd3f71b11220c26966d24d', 'S': 'BUY', 'o': 'LIMIT', 'f': 'GTC', 'q': '1', 'p': '0.10559', 'ap': '0.10559', 'sp': '0', 'x': 'TRADE', 'X': 'FILLED', 'i': 221426617, 'l': '1', 'z': '1', 'L': '0.10559', 'n': '0.00000003', 'N': 'BNB', 'T': 1744647768318, 't': 28164100, 'b': '2.62265', 'a': '0', 'm': True, 'R': True, 'wt': 'CONTRACT_PRICE', 'ot': 'LIMIT', 'ps': 'BOTH', 'cp': False, 'rp': '0.01022615', 'pP': False, 'si': 0, 'ss': 0, 'V': 'EXPIRE_MAKER', 'pm': 'NONE', 'gtd': 0}}	
	    '''
	dfex=U.get_or_set('dfex',{})
	dfex.setdefault(d['e'], collections.deque([], maxlen=99)).append(d)
	if d['e']=='ORDER_TRADE_UPDATE' and d['o']['X']=='FILLED': #(d['o']['x']=='EXPIRED' or 
		# cancel_all_future_order(exclude_symbols=['ETHUSDT','BCHUSDT'])

		s=d['o']['s']
		t=d['o']['T']
		p=Decimal(d['o']['p'])
		q=Decimal(d['o']['q'])

		qp=py.str(p)
		if '.' in qp: # 271
			qp=qp.split('.')
			if qp[0]=='0':
				qp=qp[1].strip('0')
			else:	
				qp=f"""{qp[0].lstrip('0')}.{qp[1][:2]}"""

		
		msg=f'''B future {user}账号 {T.space.join(s)} 价格 {p} 成交! {U.zh_time(t)}  {qp} BF {user} '''
		
		if d['o']['S']=='SELL':
			notify(msg,100)
			print(N.rpc_set(print_req=1,base=f'http://127.0.0.1:1177/',ext_cmd=f"r=U.dict_pop(FK.gdst,fsymbol),F.dill_dump(FK.gdsx[fsymbol],file=fsymbol+'_gdsx_'+U.stime())",fsymbol=s))
			
		if d['o']['S']=='BUY':
			if p*q<1:
				notify(msg,4)		
			else:
				notify(msg,17)


		# N.rpc_get('U.set(1,0)',base=1122)
		# N.rpc_set(cancel_last_ord=0,base=1122)

		# N.HTTP.get(f"""http://192.168.1.3:1122/r=U.tts()""",
		# print_req=1,proxies='socks5://127.7.7.7:31080')
		return msg,U.stime(),d
	return

def gdsdin_all_boll(intervals=('5m','1m','15m','3m','12h','8h','6h','4h','2h','1h','30m')):
	dsr={}
	for symbol,din in gdsdin.items():
		# for interval,y in din.items():
		# 	if interval not in intervals:continue
		dsr[symbol]=[]
		for interval in intervals:
			y=din[interval]
			for row in y:
				if row[-1]==0:continue
				# if row[2]>row[-3]:
				if row[3]<row[-1]:
					if len(dsr[symbol])<9:
						dsr[symbol].append([symbol,interval,*row[:5],*row[-3:]])
	r=[]
	for symbol,rs in dsr.items():
		if not dsr[symbol]:print(symbol)
		r.extend(rs)
	return r

def gdsdin_all_hl(limit=10,interval='1h'):
	if limit>0:limit=0-limit
	r=[]
	for symbol,din in gdsdin.items():
		h=max(din[interval][limit:,2])# t ohlc
		l=min(din[interval][limit:,3])

		h_index = din[interval][limit:, 2].argmax()# + limit
		l_index = din[interval][limit:, 3].argmin()# + limit
		x=-1 if l_index>h_index else 1

		mh=max(din['1M'][:,2])
		ml=min(din['1M'][:,3])

		cp=din[interval][-1][4]
		t=din['1s'][-1][0]
		assert U.itime_ms()-t < 9999 # U.itime_ms(),t,U.itime_ms()-t

		row=U.adict(symbol,cp,x*a_b_b(h,l),h,h_index,l_index,l,a_b_b(mh,h),a_b_b(l,ml),mh,a_b_b(mh,ml),ml,a_b_b(h,l),a_b_b(cp,l),cp+0,symbol[:])
		
		for si in gi16:
			arr=din[si]
			# minv = numpy.min(arr[:, 3])
			min_index = numpy.argmin(arr[:, 3])
			distance = len(arr) - 1 - min_index

			row[si[:2]]=distance
		
		r.append(row)

	return r	

def get_gdsdin_values(symbol='',*cols,max_min=True,intervals=B_intervals,row_index=-1,rb_high=False,rb_low=False,sort=None):
	if not symbol:symbol=N.geta()
	if py.istr(symbol):
		if symbol not in gdsdin and not symbol.endswith('USDT'):
			symbol=symbol.upper()+'USDT'
		din=gdsdin[symbol]
	if py.isdict(symbol):
		din=symbol
	if not cols:cols=py.range(12)
	r=[]
	if py.isint(row_index):row_index=[row_index]
	for row_i in row_index:
		for interval in intervals:
			row=[interval]
			for col_index in cols:
				row.append(din[interval][row_i][col_index])
			if max_min:
				row.append(get_last_is_max_n(din[interval][:,2],din['1s'][row_i][2],))	
				row.append(a_b_b( din[interval][row_i][-3] , din['1s'][row_i][2] ,round=8))	
				row.append(get_last_is_min_n(din[interval][:,3],din['1s'][row_i][3],))	
				rb_low=True
			if rb_high:
				row.append(a_b_b(din[interval][row_i][-3], din['1s'][row_i][2] ,round=8))	 
			if rb_low:
				row.append(a_b_b(din['1s'][row_i][3] , din[interval][row_i][-1],round=8))	
			r.append(row)	
	if sort!=None:
		r.sort(key=lambda x:x[sort],reverse=1)	
	return r
din_v=din_values=get_gdsdin_values

def get_intervals_sorted_din_value(din,intervals,col_index,):
	# intervals=U.unique(intervals) # 重复
	rci=[]
	for interval in intervals:
		rci.append((din[interval][-1][col_index],interval))
	rci=py.sorted(rci,reverse=(col_index!=-1))	# False 从小到大
	return U.col(rci,1),T.join(U.float_to_str(i,6) for i in U.col(rci,0))

def gdsdin_get_col(col_index=8,row_index=-1):
	d={}
	for symbol,din in gdsdin.items():
		for interval,y in din.items():
			k=interval,y[row_index][col_index]
			U.dict_add_value_list(d,k,symbol)	
			# r.append([symbol,interval,y[row_index][col_index]])
	m=py.len(gdsdin)	
	# dkn=U.dict_value_len(d)	
	# for k,n in dkn.items():
	# 	if n==m:
	# 		d[k]=m
	r=[]
	for k,v in d.items():
		n=py.len(v)
		if n==m:v=''
		r.append([*k,n,v])		
	return r

def gdsdin_set_col(col_index=8,value=1):
	for symbol,din in gdsdin.items():
		for interval,y in din.items():
			y[:,col_index] = value
	return col_index,value

def gdsdin_row_count(m=22):
	r=[]
	for symbol,din in gdsdin.items():
		for interval,y in din.items():
			n=len(y)
			if n<m:
				r.append([symbol,interval,n])
	return r

gdsdin_set_col_8=gdsdin_set_col

def gdsdin_gdsa_remove(remove_symbols=None,skip=None,gdsa=None):
	if remove_symbols and skip and not (remove_symbols or skip):raise py.ArgumentError('remove  , skip  can not at same time')
	
	if not gdsa:gdsa=U.get('gdsa')
	
	sdin=[]
	for s,din in gdsdin.items():
		if skip and s not in skip:
			sdin.append(s)
	sdin.sort()		
	
	sa=[]
	for s,a in gdsa.items():
		if skip and s not in skip:
			sa.append(s)
	sa.sort()
	# assert sdin==sa

	if remove_symbols:
		sdin=remove_symbols
		sa=remove_symbols

	for s in sdin:
		gdsdin.pop(s)
	for s in sa:
		gdsa.pop(s)

	return U.len(sdin,sa),U.StrRepr([sdin,sa]),U.len(sdin,sa),

def gdsdin_boll_filter(intervals=gi15,m=1,other_intervals_values=True,set_gdsmh=None):
	'''   ('1M','1w','3d','1d','12h')   '''
	if py.istr(intervals):intervals=intervals.split(',')
	if set_gdsmh:
		gdsmh=U.get('gdsmh')
	r=[]
	for s,din in gdsdin.items():
		# for interval,y in din.items():
		hi=''
		hv=[]
		h=[]
		l=[]
		cp=din['1s'][-1][4]
		for interval in intervals:
			y=din[interval]
			if cp>y[-1][-3]:
				# hi+=interval+','
				# hv.append(round(y[-1][-3],8))
				h.append([interval,round(y[-1][-3],8)])
			if cp<y[-1][-1]:
				l.append([interval,round(y[-1][-1],8)])	
		n=len(h)
		if m and n>=m:
			h.sort(key=lambda x: x[1],reverse=True)
			hi=U.col(h,0)
			
			# hnv=[hn[0][1],hn[-1][1]]
			si=','.join(hi)
			iv=U.col(h,1)
			row=U.adict(s,n,cp,si,iv,)
			if other_intervals_values:
				hn=[]
				for interval in gi15:
					if interval in hi:continue
					hn.append([interval,round(din[interval][-1][-3],8)])
				hn.sort(key=lambda x: x[1],reverse=False)
				hnv=U.col(hn,1)
				if n==1:hnv=hnv[0]
				elif n>=(15-n):pass#hnv=hnv
				else:
					hnv_tmp=hnv#.copy()
					hnv=[]
					for ni in range(0,n-1):
						hnv.append(hnv_tmp[ni])
						# try:
						# except Exception as e:
						# 	return s,e,n,ni,hnv,hnv_tmp
					hnv.append(hnv_tmp[-1])
							
				row['hni']=','.join(U.col(hn,0))
				row['hnv']=hnv
				# row.extend([','.join(U.col(hn,0)),hnv,])
			row['L3d']= round( a_b_b(din['3d'][-1][3],cp) ,8) 	
			for internal in gi15:
				row[internal]= round( a_b_b(din[internal][-1][2],cp) ,8) 
				# row[internal]=int(row[internal]* 10**8)
				# row.append(a_b_b(din[internal][2],cp))
			r.append(row)
			if set_gdsmh:
				if py.istr(set_gdsmh) and set_gdsmh in hi:
					mh=gdsmh.get(s,0)
					if mh<n:gdsmh[s]=n+1


		if m and len(l)>=m:
			l.sort(key=lambda x: x[1],reverse=False)
			n=-len(l)
			si=','.join(U.col(l,0))
			iv=U.col(l,1)
			row=U.adict(s,n,cp,si,iv)
			# row[]
			for internal in gi15:
				row[internal]= round( a_b_b(din[internal][-1][3],cp) ,8) 
			r.append(row)
	# r.append(['qgb',0,0,'',[]])		

	return r		
import numpy
gdsrpc=U.get_or_set('B.gdsrpc',{})
gdsit=U.get_or_set('B.gdsit',{})

gdsdin=U.get_or_set('B.gdsdin',{})
def update_kline(din,t,o,h,l,c,v=0,d=None,s=None):
	ls=[]
	hs=[]
	if s in gdsrpc and py.isdict(gdsrpc[s]) and l<gdsrpc[s]['mtp'] and numpy.float64(l)!=din['1s'][-1][3]:
		N.post_with_new_thread(f"http://127.0.0.1:1155/r=spot_{s}({repr(l)},'{s}',t={t},ct={U.ftime()})",[din,d])


	# while din['1s'][-1][0]<(t-1000):
	# 	din['1s']=numpy.roll(din['1s'],axis=0,shift=-1)
	# 	din['1s'][-1,:]=din['1s'][-1,:]
	# 	din['1s'][-1][0]=din['1s'][-2][0]+1000
	# 	din['1s'][-1][-1]=9999
	# 	print(din['1s'][-1],d)

	y=din['1s']
	ia=numpy.where(y[:,0] == t)[0]
	if py.len(ia)==1:
		ia=ia[0]
		y[ia][:5]=t,o,h,l,c
		y[ia][8]=y[-2][8]+1
	else:
		# print(ia,end='')
		# return
		F.append('error.1s',U.stime()+f' {ia} '+repr(d)+repr([int(i) for i in y[:,0]])+'\n')

	for interval,y in din.items():
		# if interval=='1s':continue
		if interval!='1s' and y[-1][0]==t:
			y[-1][:5]=t,o,h,l,c
			y[-1][8]=y[-2][8]+1
			gdsit[(s,interval)]=''

		y[-1][4]=c
		if h>y[-1][2]:y[-1][2]=h
		if l<y[-1][3]:y[-1][3]=l

	# for interval,ms in gdims.items():
	# 	if t%ms==0:
	# 		if   interval=='1w' and t!=din['1w'][-1][0]+gdims['1d']*7:
	# 			pass
	# 		elif interval=='3d' and t!=din['3d'][-1][0]+gdims['1d']*3:
	# 			pass
	# 		elif interval=='1M' and U.ms_to_datetime(t).day!=1:
	# 			pass
	# 		else:
	# 			'din[interval]=numpy.roll(din[interval],axis=0,shift=-1)'
	# 			din[interval][-1][:5]=t,o,h,l,c
	# 			din[interval][-1][8]=din[interval][-2][8]+1
	# 			gdsit[(s,interval)]=''
	# 	else:	
	# 		din[interval][-1][4]=c
	# 		if h>din[interval][-1][2]:din[interval][-1][2]=h
	# 		if l<din[interval][-1][3]:din[interval][-1][3]=l

		cs=din[interval][-21:,4] # -21:-1 是取 倒数21 to 倒数-2 [左闭右开] 总共20 个数 

		H=din[interval][-1][2]
		L=din[interval][-1][3]
		if len(cs)<9:continue

		for cp,vn in {h:'h',l:'l',c:'c'}.items():
			cs[-1]=cp
			std=numpy.std(cs)
			ma=numpy.mean(cs)
			hb=din[interval][-1][-3]=ma+std*3
			din[interval][-1][-2]=ma
			lb=din[interval][-1][-1]=ma-std*3
			if hb>lb:
				if cp>hb:hs.append(interval)
				if cp<lb:ls.append(interval)


			if interval in ('1M','1w','3d','1d','12h','8h','6h','4h','2h','1h','30m','15m'):
				ksi=(s,interval)
				if ksi not in gdsit:gdsit[ksi]=''
				if cp>hb:
					if not 'h' in gdsit[ksi]:
						print('H',U.stime(),T.padding(s,13),T.padding(interval,3),t,cp,'>',hb)
						gdsit[ksi]+='h'
					
				if cp<lb :
					if not 'l' in gdsit[ksi]:
						print('L',U.stime(),T.padding(s,13),T.padding(interval,3),t,cp,'<',lb)
						gdsit[ksi]+='l'
					

	# if t%(1000*60)==0:
	# 	din['1m']=numpy.roll(din['1m'],axis=0,shift=-1)
	# 	din['1m'][-1][:5]=t,o,h,l,c #=numpy.pad([t,o,h,l,c],(0,7),mode='constant')
	# if t%(1000*60*3)==0:
	# 	din['3m']=numpy.roll(din['3m'],axis=0,shift=-1)
	# 	din['3m'][-1][:5]=t,o,h,l,c
	hs=U.unique(hs)
	ls=U.unique(ls)
	# return
	nhs=len(hs)
	nls=len(ls)
	sr=repr(hs)+repr(ls)
	if nhs>=U.get_or_set(-3,4):
		sr='H',nhs,U.stime(),T.padding(s,13),h.normalize().to_eng_string(),*get_intervals_sorted_din_value(din,hs,-3)
		sr=T.join(sr,separator=' ')
		print(sr)
		F.append(s,sr+'\n')

	if nls>=U.get_or_set(-1,3):
		sr='L',nls,U.stime(),T.padding(s,13),l.normalize().to_eng_string(),*get_intervals_sorted_din_value(din,ls,-1)
		sr=T.join(sr,separator=' ') # repr(sr)[1:-1]
		print(sr)
		F.append(s,sr+'\n')
		# print('L',U.stime(),T.padding(s,13),l,ls)
	if nhs>7 or nls>6:
		F.append(f'n{nhs+nls}',sr+'\n')

	percent=(h-l)/l	
	if percent>0.02:
		F.append(f'h-l_2',f'{U.stime()} {percent} {sr} {repr(d)}\n')
	return

gdkline=U.get_or_set('B.gdkline',{})
# from decimal import Degtcimal as float
def process_kline_dict(d):
	# global gdh,gdl
	# t=d['E']
	# d['E']=str(t)+ U.stime(t)[4:]

	k=d['k']
	s=k['s']
	t=k['t']
	o=Decimal(k['o'])
	h=Decimal(k['h'])
	l=Decimal(k['l'])
	c=Decimal(k['c'])

	if s in gdsdin:
		din=gdsdin[s]
		update_kline(din,t,o,h,l,c,d=d,s=s)

	if s in gdkline and 'lc' in gdkline[s]:
		if h>gdkline[s]['h']:
			gdkline[s]['h']=h
			gdkline[s]['ht']=k['t']

			# gdh=U.set(1,d)
		if l<gdkline[s]['l']:
			gdkline[s]['l']=l
			gdkline[s]['lt']=k['t']
			# gdl=U.set(0,d)
		gdkline[s]['n']+=1	
		gdkline[s]['lc']=l
	else:
		gdkline[s]={'h':h,'ht':k['t'],'l':l,'lt':k['t'],'lc':l,'n':1}
	return

