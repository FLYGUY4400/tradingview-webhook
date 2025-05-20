from decimal import Decimal
import os

class VolumeProfileBreakout:
    def __init__(self, bot):
        self.bot = bot
        self.pdpoc = Decimal(os.getenv("PDPOC", "0"))
        self.pdvah = Decimal(os.getenv("PDVAH", "0"))
        self.pdval = Decimal(os.getenv("PDVAL", "0"))
        self.retest_buffer = Decimal("1.0")  # Optional: small allowance for retest entries

    def on_trade(self, price: Decimal):
        if self.bot.current_position == 0:
            if price > self.pdvah:
                self.bot.place_trade("buy", price)
            elif price < self.pdval:
                self.bot.place_trade("sell", price)
            elif price > self.pdpoc + self.retest_buffer:
                self.bot.place_trade("buy", price)
            elif price < self.pdpoc - self.retest_buffer:
                self.bot.place_trade("sell", price)

        elif self.bot.current_position > 0:
            # Exit long if price pulls back below the breakout zone
            if price < self.pdvah - self.retest_buffer:
                self.bot.place_trade("sell", price)
            elif price < self.pdpoc - self.retest_buffer:
                self.bot.place_trade("sell", price)

        elif self.bot.current_position < 0:
            # Exit short if price pulls back above the breakdown zone
            if price > self.pdval + self.retest_buffer:
                self.bot.place_trade("buy", price)
            elif price > self.pdpoc + self.retest_buffer:
                self.bot.place_trade("buy", price)


