/// <reference types="node" />
import { MavLinkData } from 'mavlink-mappings';
import { MavLinkProtocolV2 } from './mavlink';
/**
 * Serialize and deserialize a command into selected class
 */
export declare function reserialize(command: MavLinkData): {
    protocol: MavLinkProtocolV2;
    buffer: Buffer;
    header: import("./mavlink").MavLinkPacketHeader;
    payload: Buffer;
    data: MavLinkData;
};
//# sourceMappingURL=debug.d.ts.map