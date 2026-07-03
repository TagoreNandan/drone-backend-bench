"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MavTCP = void 0;
const events_1 = require("events");
const net_1 = require("net");
const stream_1 = require("stream");
const mavlink_1 = require("./mavlink");
const mavlink_2 = require("./mavlink");
/**
 * Encapsulation of communication over TCP
 */
class MavTCP extends events_1.EventEmitter {
    input;
    socket;
    ip = '127.0.0.1';
    port = 5760;
    seq = 0;
    /**
     * @param splitter packet splitter instance
     * @param parser packet parser instance
     */
    constructor({ splitter = new mavlink_1.MavLinkPacketSplitter(), parser = new mavlink_1.MavLinkPacketParser(), } = {}) {
        super();
        this.input = new stream_1.PassThrough();
        this.processIncomingTCPData = this.processIncomingTCPData.bind(this);
        this.processIncomingPacket = this.processIncomingPacket.bind(this);
        // Create the reader as usual by piping the source stream through the splitter
        // and packet parser
        const reader = this.input
            .pipe(splitter)
            .pipe(parser);
        reader.on('data', this.processIncomingPacket);
    }
    /**
     * Start communication with the controller via MAVESP8266
     *
     * @param receivePort port to receive messages on (default: 14550)
     * @param sendPort port to send messages to (default: 14555)
     * @param ip IP address to send to in case there is no broadcast (default: empty string)
     */
    async start(host = '127.0.0.1', port = 5760) {
        if (this.socket)
            throw new Error('Already connected');
        this.ip = host;
        this.port = port;
        // Create a TCP socket to connect to SITL
        this.socket = new net_1.Socket();
        this.socket.on('data', this.processIncomingTCPData);
        this.socket.once('close', () => this.emit('close'));
        // Start listening on the socket
        return new Promise((resolve, reject) => {
            this.socket?.connect(this.port, host, async () => {
                resolve({ ip: this.ip, port: this.port });
            });
        });
    }
    /**
     * Closes the client stopping any message handlers
     */
    async close() {
        if (!this.socket)
            throw new Error('Not connected');
        // Unregister event handlers
        this.socket.off('data', this.processIncomingTCPData);
        // Close the socket
        return new Promise(resolve => {
            this.socket?.end(resolve);
            this.socket = undefined;
        });
    }
    /**
     * Send a packet
     *
     * @param msg message to send
     * @param sysid system id
     * @param compid component id
     */
    async send(msg, sysid = mavlink_2.MavLinkProtocol.SYS_ID, compid = mavlink_2.MavLinkProtocol.COMP_ID) {
        const protocol = new mavlink_2.MavLinkProtocolV2(sysid, compid);
        const buffer = protocol.serialize(msg, this.seq++);
        this.seq &= 255;
        return this.sendBuffer(buffer);
    }
    /**
     * Send a signed packet
     *
     * @param msg message to send
     * @param sysid system id
     * @param compid component id
     * @param linkId link id for the signature
     */
    async sendSigned(msg, key, linkId = 1, sysid = mavlink_2.MavLinkProtocol.SYS_ID, compid = mavlink_2.MavLinkProtocol.COMP_ID) {
        const protocol = new mavlink_2.MavLinkProtocolV2(sysid, compid, mavlink_2.MavLinkProtocolV2.IFLAG_SIGNED);
        const b1 = protocol.serialize(msg, this.seq++);
        this.seq &= 255;
        const b2 = protocol.sign(b1, linkId, key);
        return this.sendBuffer(b2);
    }
    /**
     * Send raw data over the socket. Useful for custom implementation of data sending
     *
     * @param buffer buffer to send
     */
    async sendBuffer(buffer) {
        return new Promise((resolve, reject) => {
            this.socket?.write(buffer, (err) => {
                if (err)
                    reject(err);
                else
                    resolve(buffer.length);
            });
        });
    }
    processIncomingTCPData(buffer) {
        // pass on the data to the input stream
        this.input.write(buffer);
    }
    processIncomingPacket(packet) {
        // let the user know we received the packet
        this.emit('data', packet);
    }
}
exports.MavTCP = MavTCP;
