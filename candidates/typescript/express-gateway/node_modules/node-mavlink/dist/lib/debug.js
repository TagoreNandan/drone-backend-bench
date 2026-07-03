"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.reserialize = void 0;
const mavlink_1 = require("./mavlink");
/**
 * Serialize and deserialize a command into selected class
 */
function reserialize(command) {
    const protocol = new mavlink_1.MavLinkProtocolV2(mavlink_1.MavLinkProtocol.SYS_ID, mavlink_1.MavLinkProtocol.COMP_ID);
    const buffer = protocol.serialize(command, 1);
    const header = protocol.header(buffer);
    const payload = protocol.payload(buffer);
    const data = protocol.data(payload, command.constructor);
    return {
        protocol,
        buffer,
        header,
        payload,
        data,
    };
}
exports.reserialize = reserialize;
