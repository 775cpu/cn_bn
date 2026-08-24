import numpy
from decimal import Decimal

import sys;'qgb.U' in sys.modules or sys.path.append('/home/qgb/')
from qgb import py,U,T,N,F,A
B=U.import_from_file('/home/qgb/bn/B.py')

ka=F.dill_load_bytes(U.des_decrypt(
b'\x9a5\xc3\xb3^_\xad\xa2\x81\xad\xf3\xf6:\xd3\xbfN\x8di\xb7\x05\xc9\xcc\x9d9>\x02\xd9 \xde\xf5\xbc\x08f\x17c\xd4E\x10\xb8\x8f\x9d\xc41\x04[\x12\xbc\x16\xbb\\\xe0\xa1K\x05\xa1\xc9\xd2y\xda\xf2\x86\xa6\xd5\xc92\xbf\xc5\x86p\x04a\xdf\x1a\x04g\xa7\x89r/\xebDgu\x0b\x9d\xd9?$\xe7\xf9VX^\xff)\xe8\xd5\xc6\xd2\x0cs\x86\xd16\xa6\xa1e\xbc\x1c\x19\xf0=\xc0K\xb5\xcc\n\xc9\x00L\xa7N\xb7\xca\x0e\x84\xf4\x08\xe9F\xfe\x08\xc1|E\x18\x0c\xb6\x16\xa9\xf1\xd8Y\xf6\xb5\x0b{\x05\r<`\xb6r\xac\xe0\xa02\x10&\x07s.3\xed\xba$\x1c\xe9\xfb|ZI\xa9\xfc\xce\x16\xe2[\xf7H\nB\xe3h'
# ,U.input('pw:'),
,T.sub_last(F.get_home(),'/','/'),
))

from binance import AsyncClient
ac=AsyncClient(**ka)

from binance.ws.streams import BinanceSocketManager # 1.0.24  2024-11-30
bm = BinanceSocketManager(ac)

gds_okx=U.get_or_set('gds_okx',{})
# gd_okx=U.get_or_set('gd_okx',{})
# try:
def init_okx(init_d3=None,dsd=None):
	# global gc_okx
	if init_d3:
		assert len(init_d3)==3
		import okx.Trade
		c=okx.Trade.TradeAPI(**init_d3,flag='0')
		gds_okx['c']=c
	c=gds_okx['c']

	if dsd:
		for symbol,d in dsd.items():
			d['px']=Decimal(d['px'])
			gds_okx[symbol]=d
			
	# else:
	return c,c.get_order_list()
# except Exception as e_okx:print(e_okx)
def process_order_okx(s,cp,l,h):
	if 'c' in gds_okx and s in gds_okx :
		c=gds_okx['c']
		d=gds_okx[s]
	else:return py.No('c,s not in gds_okx')

	if 'n' in d:d['n']+=1
	else:d['n']=1
	# print(s,c,cp,l,h,len(d))
	try:
		if l*Decimal('0.996')<d['px']:
			d['px']=l*Decimal('0.994')
			rd=c.amend_order(d['instId'],ordId=d['ordId'],newPx=B.round_price_quantity(symbol=s,price=d['px']))
			print(U.stime(),rd)
	except Exception as e:
		print(process_order_okx,s,e)
	return 


gdtop_l=U.get_or_set('gdtop_l',U.LimitSizeSortedDict(max_size=999))	
def get_gdtop_l(symbol_filter=None):
	r=[]
	for hl,d in gdtop_l.items():
		if symbol_filter and d['k']['s'] not in symbol_filter:continue
		d=d.copy()
		d['hl']=hl
		d['E']=B.ms_to_pandas_Timestamp(d['E'])
		k=d.pop('k')
		d.update(k)
		r.append(d)
	return r

gdsmh=U.get_or_set('gdsmh',{}) #gdsm_print
gdsml=U.get_or_set('gdsml',{}) #gdsm_print

def update_m(**ka):
	for s,v in ka.items():
		if s[0].islower():s=s[1:]
		assert py.isint(v) and s in gdsn
		# if not py.isint(v):raise py.ArgumentError(s,v)
	for s,v in ka.items():
		if s.startswith('l'):
			s=s[1:]
			gdsml[s]=v

		if s.startswith('h'):
			s=s[1:]
		gdsmh[s]=v
	return ka


def insert_to_sorted_limit_list(a,limit,data):
	if not data:
		data.append(a)
	else:
		low = 0
		high = len(data) - 1
		while low <= high:
			mid = (low + high) // 2
			if data[mid] < a:
				low = mid + 1
			else:
				high = mid - 1
		data.insert(low, a)

		if len(data) > limit:
			del data[-1]
	return data
gdnc={}
gdnd={}

async def futures_multiplex_socket(symbol='BTCUSDT',interval='1m'):
	global key,d,res,streams,ts
	# streams = [f"{symbol.lower()}@kline_{interval}"]
	ts = bm.futures_multiplex_socket(['btcusdt@kline_1m','api3usdt@kline_1m','ethusdt@kline_1m','ctsiusdt@kline_1m',])
	async with ts as tscm:
		while True:
			d = await tscm.recv()
			E=d['data']['E']
			t=d['data']['k']['t']
			n=E-t
			ms=U.ftime()*1000
			m=ms-t
			d['ms']=ms
			# insert_to_sorted_limit_list(n,99,gn)
			# if n in gn:gdnd[n]=d
			if n<432 or n > 60*1000+560:
				U.dict_key_count(gdnc,n)
				gdnd[n]=d

			if U.itime()%600 in [0,1,2]:
				print(d)
			# if stream_binance['stream'] == 'btcusdt@kline_1m':
			# 	print('ohlcv processed')
	return

gdsrpc=U.get_or_set('B.gdsrpc',{})
gdsit=U.get_or_set('B.gdsit',{})
gdims={'1s': 1000,
 '1m':  1000*60,
 '3m':  1000*60*3,
 '5m':  1000*60*5,
 '15m': 1000*60*15,
 '30m': 1000*60*30,
 '1h':  1000*60*60,
 '2h':  1000*60*60*2,
 '4h':  1000*60*60*4,
 '6h':  1000*60*60*6,
 '8h':  1000*60*60*8,
 '12h': 1000*60*60*12,
 '1d':  1000*60*60*24,
 '3d':  1000*60*60*24, # *3
 '1w':  1000*60*60*24, # *7
 '1M':  1000*60*60*24, #
 }

gdsdin=U.get_or_set('gdsdin.futures',{})


gdkline=U.get_or_set('B.gdkline',{})
def process_kline_futures(symbol,d):
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

async def kline_socket_task_futures(symbol='BTCUSDT',interval='1m'):
	'''

{'e': 'continuous_kline', 'E': 1706265482754, 'ps': 'UMAUSDT', 'ct': 'PERPETUAL', 
'k': {'t': 1706265480000, 'T': 1706265539999, 'i': '1m', 'f': 3889834517107, 'L': 3889834874846, 'o': '5.566000', 'c': '5.563000', 
	'h': '5.567000', 'l': '5.563000', 'v': '4721', 'n': 112, 'x': False, 'q': '26272.772000', 'V': '2186', 'Q': '12166.673000', 'B': '0'}}	
	'''
	global key,d,res,streams,ts

	ts = bm.kline_futures_socket(symbol=symbol.upper(),interval=interval)

	async with ts as tscm:
		while True:
			d = await tscm.recv()

			try:
				process_kline_futures(symbol,d)
			except Exception as e:
				t=U.stime()
				print(symbol,interval,t,d,e)   
				if (not py.isdict(d)) or d['e']!='kline':
					gdsa[symbol]=[t,d,e,gdsa[symbol]]
					gtodo_symbol_list.append(symbol)
					return

			if U.itime()%60 in [0,1,2]:
				print(d)
			
	return


async def kline_socket_task(symbol='BTCUSDT',interval='1s'):
	'''
{'e': 'error', 'm': 'Max reconnect retries reached'}	
	'''
	# global d,ts
	# d=123
	ts = bm.kline_socket(symbol=symbol, interval=interval)
	async with ts as tscm:
		while True:
			d = await tscm.recv()
			try:
				# B.process_kline_dict(d)
				process_kline_dict(symbol,d)
			except Exception as e:
				t=U.stime()
				print(symbol,interval,t,d,e)   
				if (not py.isdict(d)) or d['e']!='kline':
					gdsa[symbol]=[t,d,e,gdsa[symbol]]
					gtodo_symbol_list.append(symbol)
					return
				

def get_intervals_sorted_din_value(din,intervals,col_index,):
	# intervals=U.unique(intervals) # 重复
	rci=[]
	for interval in intervals:
		rci.append((din[interval][-1][col_index],interval))
	rci=py.sorted(rci,reverse=(col_index!=-1))	# False 从小到大
	return U.col(rci,1),T.join(U.float_to_str(i,6) for i in U.col(rci,0))


gdsn=U.get_or_set('gdsn',{})
def process_kline_dict(symbol,d):
	# global gdh,gdl
	

	U.dict_key_count(gdsn,symbol)
	k=d['k']
	s=k['s']
	t=k['t']
	o=Decimal(k['o'])
	h=Decimal(k['h'])
	l=Decimal(k['l'])
	c=Decimal(k['c'])

	hl,sl=B.abb(h,l,round=5),T.padding(l.normalize().to_eng_string(),8)
	gdtop_l[hl]=d
	if s not in gdsdin:return
	din=gdsdin[s]
	ls=[]
	hs=[]

	# if s in gdsrpc and py.isdict(gdsrpc[s]) and l<gdsrpc[s]['mtp'] and numpy.float64(l)!=din['1s'][-1][3]:
	# 	N.post_with_new_thread(f"http://127.0.0.1:1155/r=spot_{s}({repr(l)},'{s}',t={t},ct={U.ftime()})",[din,d])

	y=din['1s']
	ia=numpy.where(y[:,0] == t)[0]
	if py.len(ia)==1:
		ia=ia[0]
		y[ia][:5]=t,o,h,l,c
		y[ia][8]=y[ia-1][8]+1
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

		cs=din[interval][-21:,4] # -21:-1 是取 倒数21 to 倒数-2 [左闭右开] 总共20 个数 

		H=din[interval][-1][2]
		L=din[interval][-1][3]
		if len(cs)<9:
			din[interval][-1][-3]=99999999
			din[interval][-1][-2]=0
			din[interval][-1][-1]=0

			continue

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
						# print('H',U.stime(),T.padding(s,13),T.padding(interval,3),t,cp,'>',hb)
						gdsit[ksi]+='h'
					
				if cp<lb :
					if not 'l' in gdsit[ksi]:
						print('L',U.stime(),T.padding(s,13),T.padding(interval,3),t,cp,'<',lb)
						gdsit[ksi]+='l'
					
	hs=U.unique(hs)
	ls=U.unique(ls)
	# return
	nhs=len(hs)
	nls=len(ls)

	if symbol in gds_okx:process_order_okx(symbol,cp=c,l=l,h=h,)

	sr=repr(hs)+repr(ls)
	if nhs>= U.dict_get_or_set(gdsmh,s,default=U.get_or_set(-3,4)):
		sr='H',nhs,U.stime(),T.padding(s,13),h.normalize().to_eng_string(),*get_intervals_sorted_din_value(din,hs,-3)
		sr=T.join(sr,separator=' ')
		print(sr)
		F.append(s,sr+'\n')

	if nls>=U.dict_get_or_set(gdsml,s,default=U.get_or_set(-1,3)):
		d['nhs']=nhs
		d['nls']=nls
		d['k']['hs']=hs
		d['k']['ls']=ls
		m1s=['1000SATSUSDT','AKROUSDT','BONKUSDT','CREAMUSDT','FLOKIUSDT','GFTUSDT','LOOMUSDT','MEMEUSDT','OAXUSDT','PEOPLEUSDT','PEPEUSDT','REIUSDT','SHIBUSDT','VTHOUSDT']
		if nls!=1 or hl>0.002 or (hl>0.00005 and s in m1s):
			sl=sl,hl
		# else:sl=[sl]
			sr=f'L {nls} {U.stime()} {T.padding(s,13)}',*sl,*get_intervals_sorted_din_value(din,ls,-1)
			sr=T.join(sr,separator='\t') # repr(sr)[1:-1]
			print(sr)
			if nls>1:
				F.append(s,sr+'\n')
		
	if nhs>7 or nls>6:
		F.append(f'n{nhs+nls}',sr+'\n')

	percent=(h-l)/l	
	if percent>0.02:
		F.append(f'h-l_2',f'{U.stime()} {percent} {sr} {repr(d)}\n')
	return


import asyncio
# gtodo_symbol_list=U.get_or_set('gtodo_symbol_list',['BTCUSDT'])
gtodo_symbol_list=U.get_or_set('gtodo_symbol_list',[])
gdsa=U.get_or_set('gdsa',{})
gdsdin=U.get_or_set('B.gdsdin',{})
gdims={'1s': 1000,
 '1m':  1000*60,
 '3m':  1000*60*3,
 '5m':  1000*60*5,
 '15m': 1000*60*15,
 '30m': 1000*60*30,
 '1h':  1000*60*60,
 '2h':  1000*60*60*2,
 '4h':  1000*60*60*4,
 '6h':  1000*60*60*6,
 '8h':  1000*60*60*8,
 '12h': 1000*60*60*12,
 '1d':  1000*60*60*24,
 '3d':  1000*60*60*24, # *3
 '1w':  1000*60*60*24, # *7
 '1M':  1000*60*60*24, #
 }
gmin_row_count=22


from time import time as ftime
import collections
gx=U.get_or_set('gx',collections.deque([],maxlen=999))
async def periodic_function(t,n=0):
	try:
		for symbol,din in gdsdin.items():
			for interval,ms in gdims.items():
				tms=t%ms
				if tms==0:
					if   interval=='1w' and t!=din['1w'][-1][0]+gdims['1d']*7:
					# (t-4*gdims['1d'])%ms!=0: # every day , not week
						pass
					elif interval=='3d' and t!=din['3d'][-1][0]+gdims['1d']*3:
						pass
					elif interval=='1M' and U.ms_to_datetime(t).day!=1:
						pass
					else:
						if len(din[interval])<gmin_row_count:
							din[interval]=numpy.vstack([din[interval],din[interval][-1]])
						else:	
							din[interval]=numpy.roll(din[interval],axis=0,shift=-1)
						din[interval][-1][0]=t
				# nt=t//ms+1
				# din[interval][-1][5]=(nt*ms-t)//1000
				din[interval][-1][5]=round(1-tms/ms,3)
	except Exception as e:
		print(U.stime(),e)
	f=ftime()
	gx.append([n,f-n,f])

async def sleep_1(n):
	while ftime()<n:
		await asyncio.sleep(0.05)

async def every_second_loop():
	global gn
	gn=ftime()//1
	while True:
		await asyncio.gather(
			sleep_1(gn+1),
			periodic_function(gn*1000,gn),
		)
		gn+=1 # make last value at din[i][-1]


# ge = U.get_or_set('kline asyncio.Event()',lazy_default=lambda :asyncio.Event())
async def main():
	asyncio.create_task(every_second_loop())
	while True:
		if not gtodo_symbol_list:
			await asyncio.sleep(1)
			continue
		# ge.clear()
		for symbol in gtodo_symbol_list:
			if symbol in gdsa:
				print(U.stime(),'skip',symbol)
			else:
				print(U.stime(),'running...',symbol)
				if symbol.isupper():
					gdsa[symbol]=asyncio.create_task(kline_socket_task(symbol,'1s'))
				else:	
					gdsa[symbol]=asyncio.create_task(kline_socket_task_futures(symbol,))
			gtodo_symbol_list.remove(symbol)
			# 
			# await atask

if __name__ == "__main__":
	for gport in [1122,1133,1144,1155,1166,1177,1188,1199,U.pid]:
		if not N.check_local_port_listen(gport):break
	N.rpcServer(globals=globals(),locals=locals(),port=gport)
	U.set_gst(f'/home/qgb/.cache/{gport}')
	# U.sleep(1)
	U.disable_log()

	# ge.set()
	# gam=asyncio.create_task(main())
	loop = asyncio.get_event_loop()
	loop.run_until_complete(main())
	# loop.run_forever()

