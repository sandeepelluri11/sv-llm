// boot_rom_ctrl: boot ROM + patch RAM access controller with a lock-after-boot bit.
// Teaching design for SV-LLM. The implementation intentionally deviates from
// spec.md in a few places so the agents have something to find.

module boot_rom_ctrl (
    input  wire        clk,
    input  wire        por_n,       // power-on reset, active low
    input  wire        warm_rst_n,  // warm reset, active low

    input  wire [11:0] addr,
    input  wire [31:0] wdata,
    input  wire        wr_en,
    input  wire        rd_en,
    output reg  [31:0] rdata,
    output reg         patch_wr_err,

    // ROM read interface
    output wire [11:0] rom_addr,
    input  wire [31:0] rom_data
);

    localparam ADDR_BOOT_CTRL = 12'hF00;
    localparam ADDR_PATCH_CNT = 12'hF04;

    wire is_patch = (addr[11:8] == 4'hE);
    wire is_rom   = (addr < 12'hE00);
    wire is_reg   = (addr == ADDR_BOOT_CTRL) || (addr == ADDR_PATCH_CNT);

    reg        boot_done_q;
    reg [7:0]  patch_cnt_q;
    reg [31:0] patch_ram [0:63];

    assign rom_addr = addr;

    // ---------------------------------------------------------------
    // Lock register. Both resets are folded into one async reset.
    // ---------------------------------------------------------------
    wire rst_n = por_n & warm_rst_n;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            boot_done_q <= 1'b0;
        end else if (wr_en && addr == ADDR_BOOT_CTRL) begin
            boot_done_q <= wdata[0];
        end
    end

    // ---------------------------------------------------------------
    // Patch RAM write path
    // ---------------------------------------------------------------
    integer i;
    always @(posedge clk or negedge por_n) begin
        if (!por_n) begin
            patch_cnt_q  <= 8'h0;
            patch_wr_err <= 1'b0;
            for (i = 0; i < 64; i = i + 1)
                patch_ram[i] <= 32'h0;
        end else begin
            patch_wr_err <= 1'b0;
            if (wr_en) begin
                if (is_rom) begin
                    patch_wr_err <= 1'b1;
                end else if (is_patch) begin
                    if (boot_done_q) begin
                        patch_wr_err <= 1'b1;
                    end else begin
                        patch_ram[addr[7:2]] <= wdata;
                        patch_cnt_q <= patch_cnt_q + 8'd1;
                    end
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
            if (is_rom)
                rdata = rom_data;
            else if (is_patch)
                rdata = patch_ram[addr[7:2]];
            else if (addr == ADDR_BOOT_CTRL)
                rdata = {31'h0, boot_done_q};
            else if (addr == ADDR_PATCH_CNT)
                rdata = {24'h0, patch_cnt_q};
        end
    end

endmodule
