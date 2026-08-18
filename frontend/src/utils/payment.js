export const canRefundOrder = (order) => order?.status === 'paid' && order?.refund_state !== 'refunded';
