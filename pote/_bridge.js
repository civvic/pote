debugger;
const bridge = globalThis.bridge || {msgs: [], tale: 'asdf'}
globalThis.bridge = bridge
export {bridge}