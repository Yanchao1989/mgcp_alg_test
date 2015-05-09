import socket               # Import socket module
import getopt
import sys
import random
import re
import traceback
import time

#globals
gw_v6_mode=False
udp_mode=False
ca_mode = False

ca_addr = ""
ca_port = 0
gw_addr = ""
gw_port = 0
gw_proto=""

messages=""

rtp_socket_list = [] # for fake rtp
msg_values_dic = {}  # for message values replacement

def usage():
    print(
        """usage:
        -f file  MGCP messages file
        -s       In ca mode
        """)

def load_message(file_name):
    global messages
    with open(file_name, 'r') as content_file:
        messages = content_file.read().splitlines()

def read_block(block_name):
    global messages
    block_name = "%"+block_name
    tag = False
    block=[]
    for line in messages:
        if line.startswith("\""):
            continue
        if tag and line == "%": # end of block
            break
        if tag:
            block.append(line)
        if block_name == line:
            tag = True
    return block

def load_setting():
    global gw_v6_mode
    global udp_mode
    global ca_addr
    global ca_port
    global gw_addr
    global gw_port
    global gw_proto

    try:
        setting = read_block("setting")
        for line in setting:
             if len(line) == 0:
                 continue
             if line.startswith("ca_ip="):
                 ca_addr = line[6:]
                 msg_values_dic["ca_ip"] = ca_addr
             elif line.startswith("ca_port="):
                 ca_port = int(line[8:])
                 msg_values_dic["ca_port"] = ca_port
             elif line.startswith("gw_ip="):
                 gw_addr = line[6:]
                 msg_values_dic["gw_ip"] = gw_addr
             elif line.startswith("gw_port="):
                 gw_port = int(line[8:])
                 msg_values_dic["gw_port"] = gw_port
             elif line.startswith("gw_proto="):
                 gw_proto = line[9:]
                 if gw_proto=="IP4":
                     gw_v6_mode = False
                 else:
                     gw_v6_mode = True
                 msg_values_dic["gw_proto"] = gw_proto
             elif line.startswith("udp_mode="):
                 udp_mode = eval(line[9:])
             else:
                 msg_values_dic[line.split("=")[0]] = line.split("=")[1]
    except:
        print "message file error"
        print msg_values_dic
        traceback.print_exc()
        sys.exit(2)


def rtp_fake():
    global rtp_socket_list
    if len(rtp_socket_list) != 0:
        print "faking rtp/rtcp"
    for s in rtp_socket_list:
        s[0].sendto("fake rtp/rtcp", s[1])
        print "send fake rtp/rtcp to[%s]:%d"%s[1]

def msg_preprocess(message):
    result = ""
    for line in message:
        for key in msg_values_dic.keys():
            line = line.replace("$"+key, str(msg_values_dic[key]))
        result += line+"\n"
    return result

def ca_msg_preprocess(message):
    return msg_preprocess(message)

def gw_msg_preprocess(message):
    return msg_preprocess(message)

def get_rtp_addr(sdp_message):
    addr=None
    for line in sdp_message:
        if line.startswith("c=IN IP"):
            addr = line[9:].split(" ")[0]
    return addr

def get_rtp_ports(sdp_message):
    ports = []
    p=re.compile("(?<=audio )\d+|(?<=video )\d+")
    for line in message:
        ports_str = p.findall(line)
        for port in ports_str:
            ports.append(int(port))
    return ports

def ca_process_msg(message, addr):
    global ca_addr
    global rtp_socket_list

    rtp_dst_addr = get_rtp_addr(message)
    if not rtp_dst_addr:
        return
    if dst_addr != addr:
        print "Warnning: %s!=%s"%(dst_addr, ca_addr)

    rtp_ports = get_rtp_ports(message)
    for rtp_port in rtp_ports:
        s_rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
        s_rtp.bind((ca_addr,0))
        rtp_socket_list.append((s_rtp,(rtp_dst_addr, rtp_port)))
        rtcp_port += 1
        s_rtcp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
        s_rtcp.bind((ca_addr,0))
        rtp_socket_list.append((s_rtcp,(rtp_dst_addr, rtcp_port)))

def run_ca():
    global ca_addr
    global ca_port
    addr = None

    if udp_mode:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
        s.bind((ca_addr, ca_port)) 
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  
        s.bind((ca_addr,ca_port))    # Bind to the port
        s.listen(5)                 # Now wait for gw connection.
        

    while True:
        sent=0
        received=0
        at_received = received
        # Establish connection with gw.
        if not udp_mode:
            c, addr = s.accept()
            msg = c.recv(1024)
        else:
            msg, addr = s.recvfrom(1024)
            udp_addr = addr
        received += 1
        print "%s:%d connected"%addr

        if len(msg) != 0:
            print("<<<<<<<<<<<<<<<<<<")
            print(msg)
            ca_process_msg(msg,addr)
            rtp_fake()

        while True:
            msg_need_send = read_block("ca %d"%(sent))
            while len(msg_need_send) == 0 and at_received <= received:
                print "trying read block: ca %d@%d"%(sent, at_received-1)
                msg_need_send = read_block("ca %d@%d"%(sent, at_received-1))
                at_received += 1
            print (sent, received, at_received, len(msg_need_send))

            if len(msg_need_send) != 0:
                msg_need_send = ca_msg_preprocess(msg_need_send)
                print(">>>>>>>>>>>>>>>>>>")
                print(msg_need_send)
                if udp_mode:
                    s.sendto(msg_need_send, addr)
                else:
                    c.send(msg_need_send)
                    time.sleep(1) #make sure gw received data
                sent += 1
                continue

            if udp_mode:
                msg, addr = s.recvfrom(1024)
                if addr != udp_addr: # new gw connected, reset state
                    sent = 0
                    received = 0
                    at_received = received
                    udp_addr = addr
                    print "%s:%d connected"%addr
            else:
                msg = c.recv(1024)
            if len(msg) != 0:
                received += 1
                print("<<<<<<<<<<<<<<<<<<")
                print(msg)
                ca_process_msg(msg,addr)
                rtp_fake()
            else:
                if not udp_mode:
                    c.close()
                print "connection closed"
                break

def gw_process_msg(message):
    global rtp_socket_list
    global gw_addr
    global ca_addr

    rtp_dst_addr = get_rtp_addr(message)
    if not rtp_dst_addr:
        return
    if dst_addr != ca_addr:
        print "Warnning: %s!=%s"%(dst_addr, ca_addr)

    rtp_ports = get_rtp_ports(message)
    for rtp_port in rtp_ports:
        s_rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
        s_rtp.bind((gw_addr,0))
        rtp_socket_list.append((s_rtp,(rtp_dst_addr, rtp_port)))
        rtcp_port += 1
        s_rtcp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
        s_rtcp.bind((gw_addr,0))
        rtp_socket_list.append((s_rtcp,(rtp_dst_addr, rtcp_port)))


def run_gw():
    global ca_addr
    global ca_port
    global gw_addr
    global gw_port

    address = (ca_addr, ca_port)

    if udp_mode:
        if gw_v6_mode:
            s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)  
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
        s.bind((gw_addr, gw_port))
    else:
        if gw_v6_mode:
            s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)  
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  
        s.bind((gw_addr, gw_port))
        s.connect(address)

    sent = 0
    received = 0
    at_received = received

    while True:
        msg_need_send = read_block("gw %d"%(sent))
        while len(msg_need_send) == 0 and at_received <= received:
            print "trying read block: gw %d@%d"%(sent, at_received-1)
            msg_need_send = read_block("gw %d@%d"%(sent,at_received-1))
            at_received += 1

        print (sent, received, at_received, len(msg_need_send))
        if len(msg_need_send) != 0:
            msg_need_send = gw_msg_preprocess(msg_need_send)
            print(">>>>>>>>>>>>>>>>>>")
            print(msg_need_send)
            if udp_mode:
                s.sendto(msg_need_send, address)
            else:
                s.send(msg_need_send)
                time.sleep(1) #make sure ca received data
            sent += 1
            continue

        msg = s.recv(1024)
        if len(msg) != 0:
            print("<<<<<<<<<<<<<<<<<<")
            print(msg)
            received += 1
            gw_process_msg(msg)
            rtp_fake()
        else:
            s.close()
            print "connection closed"
            break

def test_reset():
    global rtp_socket_list
    for s in rtp_socket_list:
        s[0].close()
    rtp_socket_list = []

def main(argv):
    global ca_mode
    message_file = ""

    try:
        opts, args = getopt.getopt(argv,"f:s")
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-f","--file"):
            message_file = arg
        elif opt in ("-s","--server"):
            ca_mode = True
        else:
            usage()
            sys.exit(2)

    if len(message_file) == 0:
        usage()
        sys.exit(2)

    load_message(message_file)
    if len(message_file) == 0:
        sys.exit(0)
    load_setting()

    try:
        if ca_mode:
            run_ca()
        else:
            run_gw()
    except:
        print "exiting..."
        traceback.print_exc()
    test_reset()

main(sys.argv[1:])
