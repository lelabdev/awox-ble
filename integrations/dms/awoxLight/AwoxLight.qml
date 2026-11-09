import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Io
import qs.Common
import qs.Widgets
import qs.DCommon.Widgets
import qs.Modules.Plugins

// Control Center tile: clicking it opens ccDetailContent, like VPN / Tailscale.
PluginComponent {
    id: root

    property int brightnessPct: pluginData.brightness !== undefined ? Number(pluginData.brightness) : 80
    property int warmthPct: pluginData.warmth !== undefined ? Number(pluginData.warmth) : 50
    property string selectedPreset: pluginData.preset || "Custom"
    property string lastRequest: pluginData.lastRequest || "Not yet controlled"
    property bool powerOnRequested: pluginData.powerOn !== undefined ? Boolean(pluginData.powerOn) : false
    property bool powerKnown: pluginData.powerKnown === true

    property bool brightnessDragging: false
    property bool warmthDragging: false
    property var commandQueue: []
    property string currentCommand: ""
    property string commandMessage: "Last requested settings, not verified"
    property string lastError: ""
    property bool busy: false

    ccWidgetIcon: "lightbulb"
    ccWidgetPrimaryText: "AwoX Light"
    ccWidgetSecondaryText: root.lastRequest
    ccWidgetIsActive: root.powerKnown && root.powerOnRequested
    ccDetailHeight: 370

    function remember(name, value) {
        try {
            if (root.pluginService)
                root.pluginService.savePluginData(root.pluginId || "awoxLight", name, value);
        } catch (error) {
            console.warn("AwoX Light: cannot persist", name, error);
        }
    }

    function queueCommand(action, value) {
        const argv = ["light", action];
        if (value !== undefined && value !== null)
            argv.push(String(Math.round(value)));
        root.commandQueue = root.commandQueue.concat([{argv: argv, label: action}]);
        root.lastRequest = action + (value === undefined || value === null ? "" : " " + Math.round(value));
        root.remember("lastRequest", root.lastRequest);
        root.lastError = "";
        root.commandMessage = "Sending " + root.lastRequest + "...";
        root.busy = true;
        Qt.callLater(root.startNext);
    }

    function startNext() {
        if (commandRunner.running)
            return;
        if (root.commandQueue.length === 0) {
            root.busy = false;
            return;
        }
        const item = root.commandQueue[0];
        root.commandQueue = root.commandQueue.slice(1);
        root.currentCommand = item.label;
        commandRunner.command = item.argv;
        commandRunner.running = true;
    }

    function applyPreset(preset) {
        if (preset === "bright") {
            root.brightnessPct = 100;
            root.warmthPct = 50;
        } else if (preset === "dim") {
            root.brightnessPct = 25;
            root.warmthPct = 100;
        } else if (preset === "night") {
            root.brightnessPct = 5;
            root.warmthPct = 100;
        } else {
            return;
        }
        root.selectedPreset = preset;
        // Presets adjust brightness/warmth but do not prove that power is on.
        root.remember("preset", preset);
        root.remember("brightness", root.brightnessPct);
        root.remember("warmth", root.warmthPct);
        root.queueCommand(preset);
    }

    function applyLevel(kind, value) {
        const percent = Math.max(0, Math.min(100, Math.round(value)));
        if (kind === "brightness") {
            root.brightnessPct = percent;
            root.remember("brightness", percent);
        } else {
            root.warmthPct = percent;
            root.remember("warmth", percent);
        }
        root.selectedPreset = "Custom";
        root.remember("preset", "Custom");
        root.queueCommand(kind === "brightness" ? "brightness" : "temperature", percent);
    }

    function applyPower(on) {
        root.powerOnRequested = on;
        root.powerKnown = true;
        root.remember("powerOn", on);
        root.remember("powerKnown", true);
        root.queueCommand(on ? "on" : "off");
    }

    Process {
        id: commandRunner
        running: false

        stdout: SplitParser {
            onRead: line => {
                if (line.trim())
                    root.commandMessage = line.trim();
            }
        }

        stderr: SplitParser {
            onRead: line => {
                if (line.trim())
                    root.lastError = line.trim();
            }
        }

        onExited: code => {
            if (code !== 0) {
                root.commandMessage = "Command failed";
                if (!root.lastError)
                    root.lastError = "light exited with code " + code;
            } else {
                root.commandMessage = "Command sent (state unverified)";
            }
            Qt.callLater(root.startNext);
        }
    }

    ccDetailContent: Component {
        Item {
            width: parent.width
            height: 360

            Column {
                anchors.fill: parent
                anchors.margins: Theme.spacingM
                spacing: Theme.spacingM

                Row {
                    width: parent.width
                    height: 44
                    spacing: Theme.spacingM

                    DIcon {
                        name: "lightbulb"
                        size: 25
                        color: Theme.primary
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Column {
                        width: parent.width - 145
                        spacing: 2
                        anchors.verticalCenter: parent.verticalCenter

                        StyledText {
                            text: "EGLO / AwoX"
                            font.pixelSize: Theme.fontSizeMedium
                            font.bold: true
                            color: Theme.surfaceText
                        }
                        StyledText {
                            text: "Local Bluetooth control"
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.surfaceVariantText
                        }
                    }

                    DButton {
                        text: "On"
                        iconName: "power"
                        width: 48
                        enabled: !root.busy
                        onClicked: root.applyPower(true)
                    }
                    DButton {
                        text: "Off"
                        iconName: "power_off"
                        width: 48
                        enabled: !root.busy
                        onClicked: root.applyPower(false)
                    }
                }

                Column {
                    width: parent.width
                    spacing: 1

                    Row {
                        width: parent.width
                        StyledText {
                            text: "Brightness"
                            font.pixelSize: Theme.fontSizeMedium
                            color: Theme.surfaceText
                        }
                        Item { width: parent.width - 150; height: 1 }
                        StyledText {
                            text: root.brightnessPct + "%"
                            font.pixelSize: Theme.fontSizeMedium
                            font.bold: true
                            color: Theme.primary
                        }
                    }

                    Controls.Slider {
                        id: brightnessSlider
                        width: parent.width
                        height: 32
                        from: 0
                        to: 100
                        stepSize: 1
                        value: root.brightnessPct
                        enabled: !root.busy
                        onMoved: root.brightnessPct = Math.round(value)
                        onPressedChanged: {
                            if (pressed) {
                                root.brightnessDragging = true;
                            } else if (root.brightnessDragging) {
                                root.brightnessDragging = false;
                                root.applyLevel("brightness", value);
                            }
                        }
                        background: Rectangle {
                            x: brightnessSlider.leftPadding
                            y: brightnessSlider.topPadding + brightnessSlider.availableHeight / 2 - height / 2
                            width: brightnessSlider.availableWidth
                            height: 7
                            radius: 4
                            color: Theme.surfaceContainerHigh
                            Rectangle {
                                width: brightnessSlider.visualPosition * parent.width
                                height: parent.height
                                radius: parent.radius
                                color: Theme.primary
                            }
                        }
                        handle: Rectangle {
                            x: brightnessSlider.leftPadding + brightnessSlider.visualPosition * (brightnessSlider.availableWidth - width)
                            y: brightnessSlider.topPadding + brightnessSlider.availableHeight / 2 - height / 2
                            width: 18
                            height: 18
                            radius: 9
                            color: Theme.primary
                            border.width: 2
                            border.color: Theme.surface
                        }
                    }
                }

                Column {
                    width: parent.width
                    spacing: 1

                    Row {
                        width: parent.width
                        StyledText {
                            text: "White temperature"
                            font.pixelSize: Theme.fontSizeMedium
                            color: Theme.surfaceText
                        }
                        Item { width: parent.width - 200; height: 1 }
                        StyledText {
                            text: root.warmthPct + "% warm"
                            font.pixelSize: Theme.fontSizeMedium
                            font.bold: true
                            color: Theme.primary
                        }
                    }

                    Controls.Slider {
                        id: warmthSlider
                        width: parent.width
                        height: 32
                        from: 0
                        to: 100
                        stepSize: 1
                        value: root.warmthPct
                        enabled: !root.busy
                        onMoved: root.warmthPct = Math.round(value)
                        onPressedChanged: {
                            if (pressed) {
                                root.warmthDragging = true;
                            } else if (root.warmthDragging) {
                                root.warmthDragging = false;
                                root.applyLevel("temperature", value);
                            }
                        }
                        background: Rectangle {
                            x: warmthSlider.leftPadding
                            y: warmthSlider.topPadding + warmthSlider.availableHeight / 2 - height / 2
                            width: warmthSlider.availableWidth
                            height: 7
                            radius: 4
                            color: Theme.surfaceContainerHigh
                            Rectangle {
                                width: warmthSlider.visualPosition * parent.width
                                height: parent.height
                                radius: parent.radius
                                color: Theme.primary
                            }
                        }
                        handle: Rectangle {
                            x: warmthSlider.leftPadding + warmthSlider.visualPosition * (warmthSlider.availableWidth - width)
                            y: warmthSlider.topPadding + warmthSlider.availableHeight / 2 - height / 2
                            width: 18
                            height: 18
                            radius: 9
                            color: Theme.primary
                            border.width: 2
                            border.color: Theme.surface
                        }
                    }
                }

                StyledText {
                    text: "Presets"
                    font.pixelSize: Theme.fontSizeMedium
                    font.bold: true
                    color: Theme.surfaceText
                }

                Row {
                    width: parent.width
                    height: 66
                    spacing: Theme.spacingS

                    Repeater {
                        model: [
                            {name: "Bright", action: "bright", icon: "wb_sunny"},
                            {name: "Dim", action: "dim", icon: "brightness_low"},
                            {name: "Night", action: "night", icon: "bedtime"}
                        ]

                        StyledRect {
                            required property var modelData
                            width: (parent.width - 2 * Theme.spacingS) / 3
                            height: 64
                            radius: Theme.cornerRadius
                            color: root.selectedPreset === modelData.action
                                   ? Theme.withAlpha(Theme.primary, 0.18)
                                   : Theme.surfaceContainerHigh
                            border.width: root.selectedPreset === modelData.action ? 1 : 0
                            border.color: Theme.primary

                            Column {
                                anchors.centerIn: parent
                                spacing: 4
                                DIcon {
                                    name: modelData.icon
                                    size: 21
                                    color: Theme.primary
                                    anchors.horizontalCenter: parent.horizontalCenter
                                }
                                StyledText {
                                    text: modelData.name
                                    font.pixelSize: Theme.fontSizeSmall
                                    color: Theme.surfaceText
                                    anchors.horizontalCenter: parent.horizontalCenter
                                }
                            }
                            MouseArea {
                                anchors.fill: parent
                                enabled: !root.busy
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.applyPreset(modelData.action)
                            }
                        }
                    }
                }

                StyledText {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: root.lastError ? root.lastError : root.commandMessage
                    font.pixelSize: Theme.fontSizeSmall
                    color: root.lastError ? Theme.error : Theme.surfaceVariantText
                }
            }
        }
    }
}
