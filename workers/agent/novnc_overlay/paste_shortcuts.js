import UI from "./app/ui.js";
import KeyTable from "./core/input/keysym.js";

const REMOTE_SHORTCUTS = new Map([
    ["a", { keysym: KeyTable.XK_a, code: "KeyA" }],
    ["c", { keysym: KeyTable.XK_c, code: "KeyC" }],
    ["x", { keysym: KeyTable.XK_x, code: "KeyX" }],
    ["z", { keysym: KeyTable.XK_z, code: "KeyZ" }],
    ["y", { keysym: KeyTable.XK_y, code: "KeyY" }],
]);

function currentRfb() {
    return UI && UI.rfb ? UI.rfb : null;
}

function hasRemoteFocus() {
    const activeElement = document.activeElement;
    if (!activeElement) {
        return false;
    }
    if (activeElement.id === "noVNC_clipboard_text") {
        return false;
    }
    if (activeElement.id === "noVNC_keyboardinput") {
        return true;
    }
    return typeof activeElement.closest === "function" && !!activeElement.closest("#noVNC_container");
}

function focusRemote() {
    const rfb = currentRfb();
    if (rfb && typeof rfb.focus === "function") {
        rfb.focus();
    }
    const keyboardInput = document.getElementById("noVNC_keyboardinput");
    if (keyboardInput && typeof keyboardInput.focus === "function") {
        keyboardInput.focus();
    }
}

function sendCtrlCombo(keysym, code) {
    const rfb = currentRfb();
    if (!rfb || typeof rfb.sendKey !== "function") {
        return;
    }
    rfb.sendKey(KeyTable.XK_Control_L, "ControlLeft", true);
    rfb.sendKey(keysym, code, true);
    rfb.sendKey(keysym, code, false);
    rfb.sendKey(KeyTable.XK_Control_L, "ControlLeft", false);
}

window.addEventListener(
    "keydown",
    (event) => {
        if (!event.ctrlKey || event.altKey || event.metaKey || !hasRemoteFocus()) {
            return;
        }

        const shortcut = REMOTE_SHORTCUTS.get(String(event.key || "").toLowerCase());
        if (!shortcut) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        focusRemote();
        sendCtrlCombo(shortcut.keysym, shortcut.code);
    },
    true,
);

window.addEventListener(
    "paste",
    (event) => {
        if (!hasRemoteFocus()) {
            return;
        }
        const text = event.clipboardData ? event.clipboardData.getData("text/plain") : "";
        if (!text) {
            return;
        }

        const rfb = currentRfb();
        if (!rfb || typeof rfb.clipboardPasteFrom !== "function") {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        focusRemote();
        rfb.clipboardPasteFrom(text);
        window.setTimeout(() => {
            focusRemote();
            sendCtrlCombo(KeyTable.XK_v, "KeyV");
        }, 25);
    },
    true,
);
