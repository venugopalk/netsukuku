import andns.andns as andns 
import dns.resolver as dns_resolver
import dns.rdatatype as rdatatypes
import dns.reversename as reverse

from ntk.core.andna import NULL_SERV_KEY
from ntk.core.snsd import AndnaResolvedRecord, SnsdResolvedRecord
from ntk.lib.log import logger as logging
from ntk.lib.micro import microfunc
from ntk.wrap.sock import Sock
from ntk.wrap.xtime import swait

class AndnsRequest(object):
    def __init__(self, hostname='', ntk_bit=andns.NTK_REALM,
                                    serv_key=NULL_SERV_KEY):
        self.hostname = hostname
        self.ntk_bit = ntk_bit
        self.serv_key = serv_key

class AndnsReverseRequest(object):
    def __init__(self, ip='', nip=[], ntk_bit=andns.NTK_REALM):
        # as a dotted string for internet
        self.ip = ip
        # as a sequence for netsukuku
        self.nip = nip
        self.ntk_bit = ntk_bit

class AndnsServer(object):
    def __init__(self, andna, counter, nameservers=[]):
        self.andna = andna
        self.counter = counter
        if nameservers:
            dns_resolver.default_resolver.nameservers = nameservers
        self.run()

    @microfunc(True, keep_track=1)
    def run(self, port=53):
        socket = Sock(None, None)
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(('', port))
        logging.debug('AndnsServer: binded to UDP port ' + str(port))
        self.serving_ids = []
        
        while True:
            logging.debug('AndnsServer: waiting requests.')
            message, address = self.s.recvfrom(1024)
            logging.debug('AndnsServer: serving a request.')
            self.requestHandler(address, message) 

    @microfunc(True, keep_track=1)
    def requestHandler(self, address, message):
        resp = None
        try:
            message_id = ord(message[0]) * 256 + ord(message[1])
            logging.debug('AndnsServer: msg id = ' + str(message_id))
            if message_id in self.serving_ids:
                # the request is already taken, drop this message
                logging.debug('AndnsServer: I am already serving this request.')
                return
            self.serving_ids.append(message_id)
            self.cleanup_serving_id(message_id)

            try:
                # convert to AndnsPacket instance
                msg = andns.from_wire(message)
                logging.debug('AndnsServer: received the following packet...\n'
                               + str(msg))
 
                try:
                    op = msg.qtype
                    if op == andns.AT_A:
                        # standard query
                        resp = self.std_qry(msg)
                    elif op == andns.AT_PTR:
                        # inverse query
                        resp = self.inv_qry(msg)
                    elif op == andns.AT_G:
                        # TODO: why this value is missing into the RFC?
                        # from ntkresolv.c:
                        #    "global	hostname -> all services ip"
                        raise Exception, 'AT_G: Not implemented yet'
                    else:
                        # Not Implemented
                        resp = self.make_response(qry=msg, RCODE=4)

                except Exception, e:
                    # Server Error
                    logging.info('AndnsServer: got ' + repr(e))
                    resp = self.make_response(qry=msg, RCODE=2)   
                    logging.debug('AndnsServer: resp = ' + repr(resp.to_wire()))

            except Exception, e:
                # Format Error
                logging.info('AndnsServer: got ' + repr(e))
                resp = self.make_response(id=message_id, RCODE=1)  
                logging.debug('AndnsServer: resp = ' + repr(resp.to_wire()))

        except Exception, e:
            # message was crap, not even the ID
            logging.info('AndnsServer: got ' + repr(e))

        if resp:
            self.s.sendto(resp.to_wire(), address)

    @microfunc(True)
    def cleanup_serving_id(self, message_id):
        swait(20000)
        self.serving_ids.remove(message_id)

    def resolve(self, req, no_chain=False):
        """ AndnsRequest or AndnsReverseRequest object as input.

        @rtype: AndnaResolvedRecord object.
        """
        if not isinstance(req, AndnsRequest):
            raise Exception, 'The req must be an AndnsRequest object'

        hostname, serv_key, nk = req.hostname, req.serv_key, req.ntk_bit
        logging.debug('AndnsServer: resolve hostname ' + str(hostname) +
                                   ' using serv_key ' + str(serv_key))
                                   
        if nk == andns.NTK_REALM:
            logging.debug('AndnsServer: forwarding the request in ANDNA')
            record = self.andna.resolve(hostname, serv_key, no_chain)
            logging.debug('AndnsServer: retrieved this records...\n'+
                          str(record))
            logging.debug('AndnsServer: ANDNA resolution finished.')
        elif nk == andns.INET_REALM:
            logging.debug('AndnsServer: forwarding the request in DNS')
            tcp = False # means we use UDP protocol
            # TODO: can be usefull to use TCP?
            answers = dns_resolver.query(hostname, rdatatypes.A, tcp=False)
            records = []

            logging.debug('AndnsServer: this are the answers retrieved: ')
            logging.debug(str(answers))

            for rdata in answers:
                # TODO: are there equivalent DNS info for priority and weight?
                records.append(SnsdResolvedRecord(str(rdata), 1, 1))

            record = AndnaResolvedRecord(answers.ttl, records)
            logging.debug('AndnsServer: INET resolution finished.')

        return record

    def reverse_resolve(self, req):
        if not isinstance(req, AndnsReverseRequest):
               raise Exception, 'The request must be an instance of AndnsReverseRequest'

        nk = req.ntk_bit
        if nk == andns.NTK_REALM:
            name = req.nip
        elif nk == andns.INET_REALM:
            name = req.ip

        logging.debug('AndnsServer: reverse resolve of ' + str(name))
        
        if nk == andns.NTK_REALM:
            logging.debug('AndnsServer: forwarding the request in ANDNA')
            record = self.counter.ask_reverse_resolution(name)
            logging.debug('AndnsServer: retrieved this records...\n'+
                          str(record))
            logging.debug('AndnsServer: ANDNA resolution finished.')
        elif nk == andns.INET_REALM:
            logging.debug('AndnsServer: forwarding the request in DNS ' +
                          str(name))
            
            answers = dns_resolver.query(reverse.from_address(name),
                                         rdatatypes.PTR)
            logging.debug('AndnsServer: this are the answers retrieved: ')
            logging.debug(str(answers))
            records = []

            for rdata in answers:
                # TODO: see lines 140 and 142 of this file
                records.append(SnsdResolvedRecord(str(rdata), 1, 1))
                
            record = AndnaResolvedRecord(answers.ttl, records)
            logging.debug('AndnsServer: INET resolution finished.')

        return record

    def std_qry(self, msg):
        ''' Take an AndnsPacket object as `msg' and return another object of the
        same type that is the response. '''
        if msg.qr == 0:
           # the packet contains questions
           hostname, nk, serv_key = msg.qstdata, msg.nk, msg.service

           res = self.resolve(AndnsRequest(hostname, nk, serv_key))
           for record in res.records:
               # TODO: where do you save MAIN_IP?
               # (see libandns, is missing in RFC)
               msg.addAnswer((1, record.weight, record.priority,
                                serv_key, record.record))
        else:
           return msg # This packet doesn't contains questions

        # now the packet contains answers...
        msg.qr = 1
        return msg

    def inv_qry(self, msg):
        if msg.qr == 0:
           # the packet contains questions
           name, nk, serv_key = msg.qstdata, msg.nk, msg.service
           req = None
           if nk == andns.NTK_REALM:
               req = AndnsReverseRequest(None, name, nk)
           elif nk == andns.INET_REALM:
               req = AndnsReverseRequest(name, None, nk)

           res = self.reverse_resolve(req) 
           for record in res.records:
               # TODO: where do you save MAIN_IP?
               # (see libandns, is missing in RFC)
               msg.addAnswer((1, record.weight, record.priority,
                                serv_key, record.record))
        else:
           return msg # This packet doesn't contains questions

        # now the packet contains answers...
        msg.qr = 1
        return msg

    def make_response(self, qry=None, id=None, RA=True, RCODE=0):
        ''' Makes a response, from a query or just an ID.

        @rtype: AndnsPacket object'''

        if qry is None and id is None:
            raise Exception, 'bad use of make_response'
        if qry is None:
            resp = andns.AndnsPacket(id, 1 if RA else 0, rcode=RCODE)
        else:
            qry.rcode = RCODE
            qry.ancount = 0
            resp = qry
        return resp
