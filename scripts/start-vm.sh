#!/bin/bash
set -e

VM_NAME="${VM_NAME:-40agent-vm}"
VM_DISK="${VM_DISK:-vm_data/40agent-vm.qcow2}"
QMP_SOCKET="${QMP_SOCKET:-/tmp/qemu-40agent-vm-qmp.sock}"
MEMORY="${MEMORY:-4096}"
CPUS="${CPUS:-2}"

cd "$(dirname "$0")/.."

if [ ! -f "$VM_DISK" ]; then
    echo "VM disk not found: $VM_DISK"
    echo "Create one with: qemu-img create -f qcow2 $VM_DISK 20G"
    exit 1
fi

rm -f "$QMP_SOCKET"

echo "Starting VM: $VM_NAME"
echo "QMP Socket: $QMP_SOCKET"

qemu-system-x86_64 \
    -name "$VM_NAME" \
    -m "$MEMORY" \
    -smp "$CPUS" \
    -hda "$VM_DISK" \
    -qmp "unix:$QMP_SOCKET,server,nowait" \
    -device virtio-vga \
    -usb -device usb-tablet \
    -display gtk \
    "$@"
