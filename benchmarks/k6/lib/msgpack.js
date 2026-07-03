// Minimal MessagePack decoder in pure JS for k6
export function unpack(buffer) {
  const view = new DataView(buffer);
  let offset = 0;

  function readUint8() {
    const val = view.getUint8(offset);
    offset += 1;
    return val;
  }

  function readInt8() {
    const val = view.getInt8(offset);
    offset += 1;
    return val;
  }

  function readUint16() {
    const val = view.getUint16(offset);
    offset += 2;
    return val;
  }

  function readInt16() {
    const val = view.getInt16(offset);
    offset += 2;
    return val;
  }

  function readUint32() {
    const val = view.getUint32(offset);
    offset += 4;
    return val;
  }

  function readInt32() {
    const val = view.getInt32(offset);
    offset += 4;
    return val;
  }

  function readFloat32() {
    const val = view.getFloat32(offset);
    offset += 4;
    return val;
  }

  function readFloat64() {
    const val = view.getFloat64(offset);
    offset += 8;
    return val;
  }

  function readString(len) {
    const bytes = new Uint8Array(buffer, offset, len);
    offset += len;
    // Simple UTF-8 decoder
    let str = "";
    for (let i = 0; i < bytes.length; i++) {
      str += String.fromCharCode(bytes[i]);
    }
    return str;
  }

  function readValue() {
    if (offset >= view.byteLength) {
      return null;
    }
    const type = readUint8();

    // Positive FixNum
    if (type <= 0x7f) {
      return type;
    }
    // FixMap
    if (type >= 0x80 && type <= 0x8f) {
      return readMap(type - 0x80);
    }
    // FixArray
    if (type >= 0x90 && type <= 0x9f) {
      return readArray(type - 0x90);
    }
    // FixStr
    if (type >= 0xa0 && type <= 0xbf) {
      return readString(type - 0xa0);
    }
    // Nil
    if (type === 0xc0) {
      return null;
    }
    // False
    if (type === 0xc2) {
      return false;
    }
    // True
    if (type === 0xc3) {
      return true;
    }
    // Float 32
    if (type === 0xca) {
      return readFloat32();
    }
    // Float 64
    if (type === 0xcb) {
      return readFloat64();
    }
    // Uint 8
    if (type === 0xcc) {
      return readUint8();
    }
    // Uint 16
    if (type === 0xcd) {
      return readUint16();
    }
    // Uint 32
    if (type === 0xce) {
      return readUint32();
    }
    // Int 8
    if (type === 0xd0) {
      return readInt8();
    }
    // Int 16
    if (type === 0xd1) {
      return readInt16();
    }
    // Int 32
    if (type === 0xd2) {
      return readInt32();
    }
    // Str 8
    if (type === 0xd9) {
      return readString(readUint8());
    }
    // Str 16
    if (type === 0xda) {
      return readString(readUint16());
    }
    // Str 32
    if (type === 0xdb) {
      return readString(readUint32());
    }
    // Array 16
    if (type === 0xdc) {
      return readArray(readUint16());
    }
    // Array 32
    if (type === 0xdd) {
      return readArray(readUint32());
    }
    // Map 16
    if (type === 0xde) {
      return readMap(readUint16());
    }
    // Map 32
    if (type === 0xdf) {
      return readMap(readUint32());
    }
    // Negative FixNum
    if (type >= 0xe0 && type <= 0xff) {
      return type - 0x100;
    }

    throw new Error(`Unsupported MsgPack type: 0x${type.toString(16)}`);
  }

  function readArray(len) {
    const arr = [];
    for (let i = 0; i < len; i++) {
      arr.push(readValue());
    }
    return arr;
  }

  function readMap(len) {
    const obj = {};
    for (let i = 0; i < len; i++) {
      const key = readValue();
      const val = readValue();
      obj[key] = val;
    }
    return obj;
  }

  return readValue();
}
export default { unpack };
