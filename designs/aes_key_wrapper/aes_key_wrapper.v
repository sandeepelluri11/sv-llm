// aes_key_wrapper: key register bank + control/status for an AES core.
// Teaching design for SV-LLM. The implementation intentionally deviates from
// spec.md in a few places so the agents have something to find.

module aes_key_wrapper (
    input  wire        clk,
    input  wire        rst_n,

    // system bus
    input  wire [7:0]  addr,
    input  wire [31:0] wdata,
    input  wire        wr_en,
    input  wire        rd_en,
    input  wire        priv,
    output reg  [31:0] rdata,
    output reg         access_err,

    // AES core
    input  wire        core_busy,
    output wire [127:0] key,
    output wire        key_valid,

    // debug read-back port
    input  wire [1:0]  dbg_rd_addr,
    output reg  [31:0] dbg_rd_data
);

    localparam ADDR_CTRL   = 8'h00;
    localparam ADDR_STATUS = 8'h04;
    localparam ADDR_KEY0   = 8'h10;
    localparam ADDR_KEY1   = 8'h14;
    localparam ADDR_KEY2   = 8'h18;
    localparam ADDR_KEY3   = 8'h1C;

    reg [31:0] key_q [0:3];
    reg        key_valid_q;
    reg        debug_lock_q;

    assign key       = {key_q[3], key_q[2], key_q[1], key_q[0]};
    assign key_valid = key_valid_q;

    wire is_key_addr = (addr == ADDR_KEY0) || (addr == ADDR_KEY1) ||
                       (addr == ADDR_KEY2) || (addr == ADDR_KEY3);

    // ---------------------------------------------------------------
    // Write path
    // ---------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            key_q[0]     <= 32'h0;
            key_q[1]     <= 32'h0;
            key_q[2]     <= 32'h0;
            key_q[3]     <= 32'h0;
            key_valid_q  <= 1'b0;
            debug_lock_q <= 1'b0;
            access_err   <= 1'b0;
        end else begin
            access_err <= 1'b0;
            if (wr_en) begin
                if (!priv && (addr == ADDR_CTRL || is_key_addr)) begin
                    access_err <= 1'b1;
                end else begin
                    case (addr)
                        ADDR_CTRL: begin
                            if (!core_busy)
                                key_valid_q <= wdata[0];
                            // debug_lock follows the written value directly
                            debug_lock_q <= wdata[1];
                        end
                        ADDR_KEY0: key_q[0] <= wdata;
                        ADDR_KEY1: key_q[1] <= wdata;
                        ADDR_KEY2: key_q[2] <= wdata;
                        ADDR_KEY3: key_q[3] <= wdata;
                        default: ;
                    endcase
                end
            end
        end
    end

    // ---------------------------------------------------------------
    // Read path
    // ---------------------------------------------------------------
    always @(*) begin
        rdata = 32'h0;
        if (rd_en) begin
            case (addr)
                ADDR_CTRL:   rdata = {30'h0, debug_lock_q, key_valid_q};
                ADDR_STATUS: rdata = {31'h0, core_busy};
                ADDR_KEY0:   rdata = priv ? key_q[0] : 32'h0;
                ADDR_KEY1:   rdata = priv ? key_q[1] : 32'h0;
                ADDR_KEY2:   rdata = priv ? key_q[2] : 32'h0;
                ADDR_KEY3:   rdata = priv ? key_q[3] : 32'h0;
                default:     rdata = 32'h0;
            endcase
        end
    end

    // ---------------------------------------------------------------
    // Debug read-back
    // ---------------------------------------------------------------
    always @(*) begin
        dbg_rd_data = key_q[dbg_rd_addr];
    end

endmodule
