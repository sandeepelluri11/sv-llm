// bus_arbiter: two-master round-robin arbiter with lock support.
// Teaching design for SV-LLM. The implementation intentionally deviates from
// spec.md in a few places so the agents have something to find.

module bus_arbiter (
    input  wire       clk,
    input  wire       rst_n,

    input  wire [1:0] req,
    input  wire [1:0] lock,
    input  wire       secure_only_lock,
    output reg  [1:0] grant,
    output reg        lock_timeout
);

    reg       last_q;      // last master granted, for round-robin
    reg       locked_q;    // a lock hold is in progress
    reg       owner_q;     // which master holds the lock
    reg [4:0] hold_cnt_q;  // cycles the current lock has been held

    wire [1:0] lock_eff = lock;

    wire owner_holding = locked_q && req[owner_q] && lock_eff[owner_q];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            grant        <= 2'b00;
            last_q       <= 1'b1;
            locked_q     <= 1'b0;
            owner_q      <= 1'b0;
            hold_cnt_q   <= 5'd0;
            lock_timeout <= 1'b0;
        end else begin
            lock_timeout <= 1'b0;

            if (owner_holding) begin
                // keep the bus with the lock owner
                grant      <= owner_q ? 2'b10 : 2'b01;
                hold_cnt_q <= hold_cnt_q + 5'd1;
            end else begin
                locked_q   <= 1'b0;
                hold_cnt_q <= 5'd0;

                // round-robin: prefer the master that was not served last
                if (req[~last_q]) begin
                    grant  <= (~last_q) ? 2'b10 : 2'b01;
                    last_q <= ~last_q;
                    if (lock_eff[~last_q]) begin
                        locked_q <= 1'b1;
                        owner_q  <= ~last_q;
                    end
                end else if (req[last_q]) begin
                    grant <= last_q ? 2'b10 : 2'b01;
                    if (lock_eff[last_q]) begin
                        locked_q <= 1'b1;
                        owner_q  <= last_q;
                    end
                end else begin
                    grant <= 2'b00;
                end
            end
        end
    end

endmodule
