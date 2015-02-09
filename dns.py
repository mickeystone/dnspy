#!/usr/bin/python
#coding=utf-8

DEF_LOCAL_HOST = ''
DEF_REMOTE_SERVER = '114.114.114.114'
DEF_PORT = 53
DEF_CONF_FILE = 'dnsserver.conf'
DEF_TIMEOUT = 0.4

from SocketServer import *
from socket import *
import sys, os ,re, threading
from  ConfigParser import ConfigParser

from multiprocessing import Pool



gl_remote_server = None
gl_conf_host = None

mutex = threading.Lock()

class LocalDNSHandler(BaseRequestHandler):
	def setup(self):
		global gl_conf_host
		self.hosts = gl_conf_host

	def handle(self):
		global mutex
		data, socket = self.request
		domain = self.getDomain(data)
		configIp = None

		#�Ӹ���,�Է�ֹ�ڸ�hosts��������ʱ,���� RuntimeError: dictionary changed size during iteration
		mutex.acquire()
		if '.in-addr.arpa' == domain[-13:]:
			configIp = '0.0.0.0'
		elif domain in self.hosts:
			configIp = self.hosts[domain]
		else:
			for k,v in self.hosts.iteritems():
				try:
					m =  re.search(k + r'$' , domain);
					if m:
						configIp = v
						#��������������,������hosts��,�Ա��´�������ʱֱ��ͨ�� self.hosts[domain] ����,�����������������·��
						self.hosts[domain] = v
						break
				except Exception as err:
					configIp = None
					print 'error' , err, k ,v
		mutex.release()
		if configIp != None:
			print '[%s] --> [%s]' % (domain, configIp)
			rspdata = self.respuesta(configIp, data);
		else:
			rspdata = self._getResponse(domain, data)
			#��ȡ���ݳ���ʱ,���� 0.0.0.0 ��IP
			if rspdata == 1:
				rspdata = self.respuesta('0.0.0.0', data);
		socket.sendto(rspdata, self.client_address)

	def _getResponse(self, domain, data):
		"Send client's DNS request (data) to remote DNS server, and return its response."

		remote_server = None

		global gl_remote_server
		if gl_remote_server != None:
			#��ͬ������,ʹ�ò�ͬ��DNS������ȥ���н���
			for k,v in gl_remote_server.iteritems():
				m =  re.search(k + r'$' , domain);
				if m:
					remote_server = v
					break

		if remote_server == None:
			remote_server = DEF_REMOTE_SERVER

		dnsserver = (remote_server, DEF_PORT)

		sock = socket(AF_INET, SOCK_DGRAM) # socket for the remote DNS server
		sock.connect(dnsserver)
		sock.sendall(data)
		sock.settimeout(5)
		try:
			rspdata = sock.recv(65535)
		except Exception, e:
			print e, 'ignored.'
			sock.close()
			return 1
		# "delicious food" for GFW:
		while 1:
			sock.settimeout(DEF_TIMEOUT)
			try:
				rspdata = sock.recv(65535)
			except timeout:
				#rspdata = self.respuesta('0.0.0.0' , data);
				break
		sock.close()
		return rspdata

	def getDomain(self , data):
		tipo = (ord(data[2]) >> 3) & 15   # Opcode bits
		dominio = ''
		if tipo == 0:                     # Standard query
			ini=12
			lon=ord(data[ini])
			while lon != 0:
				dominio+=data[ini+1:ini+lon+1]+'.'
				ini+=lon+1
				lon=ord(data[ini])
		return  dominio[:-1]

	def respuesta(self, ip , data):
		packet=''
		packet+=data[:2] + "\x81\x80"
		packet+=data[4:6] + data[4:6] + '\x00\x00\x00\x00'   # Questions and Answers Counts
		packet+=data[12:]                                         # Original Domain Name Question
		packet+='\xc0\x0c'                                             # Pointer to domain name
		packet+='\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04'             # Response type, ttl and resource data length -> 4 bytes
		packet+=str.join('',map(lambda x: chr(int(x)), ip.split('.'))) # 4bytes of IP
		return packet
class LocalDNSServer(ThreadingUDPServer):
	pass

def main():
	global gl_remote_server, gl_conf_host

	cf = ConfigParser()
	cf.read(DEF_CONF_FILE)

	if cf.has_section('dns'):
		gl_remote_server = {}

		for opt in cf.options('dns'):
			optv = cf.get('dns', opt).strip()
			cfg = optv.split('/')
			if len(cfg) > 1:
				gl_remote_server[cfg[0]] = cfg[1]
			else:
				DEF_REMOTE_SERVER = optv

	if cf.has_section('host'):
		gl_conf_host = {}
		for opt in cf.options('host'):
			optv  = cf.get('host' , opt).strip()
			opt = opt.replace('.' , r'\.')
			m = re.search('[?*]', opt)
			if m:
				opt = opt.replace('*', r'\w+').replace('?', r'.')
			gl_conf_host[opt] = optv
		#print gl_conf_host

	LocalDNSServer((DEF_LOCAL_HOST, DEF_PORT), LocalDNSHandler).serve_forever()

if __name__ == '__main__':
	main()
