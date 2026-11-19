"""
 Copyright (C) 2026 Raghav Subbarao

 This file is part of QuantLib, a free-software/open-source library
 for financial quantitative analysts and developers - http://quantlib.org/

 QuantLib is free software: you can redistribute it and/or modify it
 under the terms of the QuantLib license.  You should have received a
 copy of the license along with this program; if not, please email
 <quantlib-dev@lists.sf.net>. The license is also available online at
 <https://www.quantlib.org/license.shtml>.

 This program is distributed in the hope that it will be useful, but WITHOUT
 ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 FOR A PARTICULAR PURPOSE.  See the license for more details.
"""

# Tests of the wrappers of the FX pair market and vol surface of
# ql/experimental/fxslv: conventions, tenor dates, events, trading time,
# FxVarianceSurface and FxPairMarket. Dates, quotes and expected values are
# those of test-suite/fxlocalvol.cpp where it has them.

import math
import unittest

import QuantLib as ql

TODAY = ql.Date(2, ql.January, 2024)  # a Tuesday
TENORS = [ql.Period(1, ql.Weeks), ql.Period(1, ql.Months), ql.Period(3, ql.Months), ql.Period(6, ql.Months),
          ql.Period(1, ql.Years)]
DELTAS = [0.25, 0.10]
ATMS = [0.0800, 0.0820, 0.0850, 0.0900, 0.0930]
RRS = [[-0.010, -0.020], [-0.012, -0.024], [-0.014, -0.028], [-0.016, -0.031], [-0.017, -0.033]]
BFS = [[0.0035, 0.0075], [0.0040, 0.0085], [0.0045, 0.0095], [0.0050, 0.0105], [0.0055, 0.0115]]

# the pairs the market data covers: (foreign, domestic, spot, foreign rate, domestic rate, delta type);
# EURUSD and GBPUSD quote pips (spot) deltas, USDJPY premium-adjusted ones
PAIRS = {
    "EURUSD": ("EUR", "USD", 1.0850, 0.0400, 0.0525, ql.DeltaVolQuote.Spot),
    "GBPUSD": ("GBP", "USD", 1.2700, 0.0500, 0.0525, ql.DeltaVolQuote.Spot),
    "USDJPY": ("USD", "JPY", 145.00, 0.0525, 0.0010, ql.DeltaVolQuote.PaSpot),
}


def curve(rate, date=TODAY):
    return ql.YieldTermStructureHandle(ql.FlatForward(date, rate, ql.Actual365Fixed()))


def conventions(pair, flyType=ql.FxRrBfQuotes.SmileStrangle):
    foreign, domestic, _, _, _, deltaType = PAIRS[pair]
    return ql.FxPairConventions(foreign, domestic, ql.FxSettleConvention(ql.WeekendsOnly(), 2), ql.FxExpiryCut(10),
                                deltaType, ql.DeltaVolQuote.AtmDeltaNeutral, flyType)


def quotes():
    return ql.FxVolQuotes(TENORS, DELTAS, ATMS, RRS, BFS)


def market(pair, config=None, date=TODAY):
    _, _, spot, rFor, rDom, _ = PAIRS[pair]
    return ql.FxPairMarket(date, conventions(pair), spot, curve(rFor, date), curve(rDom, date), quotes(), [],
                           config or ql.FxVolSurfaceConfig(ql.FxSmileModel.Sabr, ql.FxVolInterpolation.Ncp, 0.2))


class FxConventionsTest(unittest.TestCase):

    def testTenorExpiryDates(self):
        """Cases of testFxTenorExpiryDates."""
        settlement = ql.FxSettleConvention(ql.WeekendsOnly(), 2)
        cases = [(ql.Period(1, ql.Days), ql.Date(3, 1, 2024), ql.Date(5, 1, 2024)),
                 (ql.Period(1, ql.Weeks), ql.Date(9, 1, 2024), ql.Date(11, 1, 2024)),
                 (ql.Period(1, ql.Months), ql.Date(1, 2, 2024), ql.Date(5, 2, 2024)),
                 (ql.Period(3, ql.Months), ql.Date(2, 4, 2024), ql.Date(4, 4, 2024)),
                 (ql.Period(6, ql.Months), ql.Date(2, 7, 2024), ql.Date(4, 7, 2024)),
                 (ql.Period(1, ql.Years), ql.Date(2, 1, 2025), ql.Date(6, 1, 2025))]
        for tenor, expiry, delivery in cases:
            with self.subTest(tenor=str(tenor)):
                self.assertEqual(ql.fxExpiryDate(TODAY, tenor, settlement), expiry)
                self.assertEqual(ql.fxDeliveryDate(TODAY, tenor, settlement), delivery)
        self.assertEqual(list(ql.fxExpiryDates(TODAY, [c[0] for c in cases], settlement)), [c[1] for c in cases])
        eom = ql.Date(27, 2, 2024)
        self.assertEqual(ql.fxDeliveryDate(eom, ql.Period(1, ql.Months), settlement), ql.Date(29, 3, 2024))
        with self.assertRaises(RuntimeError):
            ql.fxExpiryDate(TODAY, ql.Period(0, ql.Days), settlement)

    def testPairConventions(self):
        c = conventions("USDJPY")
        self.assertEqual(c.name(), "USDJPY")
        self.assertEqual(c.deltaType(), ql.DeltaVolQuote.PaSpot)
        self.assertEqual(c.settlement().spotLag(), 2)
        self.assertAlmostEqual(c.cut().timeOfDay(), 10 / 24, places=14)
        self.assertEqual(c.withFlyType(ql.FxRrBfQuotes.MarketStrangle).flyType(), ql.FxRrBfQuotes.MarketStrangle)
        self.assertEqual(c.flyType(), ql.FxRrBfQuotes.SmileStrangle)
        with self.assertRaises(RuntimeError):
            ql.FxPairConventions("EUR", "EUR", ql.FxSettleConvention(ql.WeekendsOnly()), ql.FxExpiryCut(10),
                                 ql.DeltaVolQuote.Spot, ql.DeltaVolQuote.AtmDeltaNeutral, ql.FxRrBfQuotes.SmileStrangle)

    def testExpiryCut(self):
        cut = ql.FxExpiryCut(10)
        d = ql.Date(5, 1, 2024)
        self.assertTrue(cut.precedes(d, 9.5 / 24, d))
        self.assertFalse(cut.precedes(d, 10 / 24, d))  # an event at the cut comes after the expiry
        with self.assertRaises(RuntimeError):
            ql.FxExpiryCut(0)

    def testVolQuotes(self):
        q = quotes()
        self.assertEqual(len(q.tenors), 5)
        self.assertEqual(list(q.atms), ATMS)
        self.assertEqual([list(r) for r in q.riskReversals], RRS)
        ql.checkFxVolQuotes(q, "EURUSD")
        bad = ql.FxVolQuotes(TENORS, DELTAS, ATMS[:-1], RRS, BFS)
        with self.assertRaises(RuntimeError):
            ql.checkFxVolQuotes(bad, "EURUSD")


class FxTradingTimeTest(unittest.TestCase):

    def testWeekendsRunSlower(self):
        tt = ql.TradingTimeTermStructure(TODAY, ql.WeekendsOnly(), 0.2)
        friday, monday = ql.Date(5, 1, 2024), ql.Date(8, 1, 2024)
        self.assertAlmostEqual(tt.tradingTime(friday, monday), 1.4 / 365, places=12)  # Fri + 0.2 Sat + 0.2 Sun
        self.assertAlmostEqual(tt.calendarTime(tt.tradingTime(0.5)), 0.5, places=10)

    def testEventsAddTradingTime(self):
        weight = ql.SimpleQuote(2.0)
        jump = ql.JumpTradingTimeEvent(ql.Date(10, 1, 2024), 0.5, ql.QuoteHandle(weight))
        tt = ql.TradingTimeTermStructure(TODAY, ql.WeekendsOnly(), 0.2, [jump])
        plain = ql.TradingTimeTermStructure(TODAY, ql.WeekendsOnly(), 0.2)
        after = ql.Date(11, 1, 2024)
        self.assertAlmostEqual(tt.tradingTime(after) - plain.tradingTime(after), 2.0 / 365, places=12)
        weight.setValue(1.0)  # the clock observes the weight
        self.assertAlmostEqual(tt.tradingTime(after) - plain.tradingTime(after), 1.0 / 365, places=12)
        self.assertEqual(len(tt.events()), 1)

    def testTradingTimeCurveKeepsDiscountFactors(self):
        tt = ql.TradingTimeTermStructureHandle(ql.TradingTimeTermStructure(TODAY))
        usd = curve(0.0525)
        ttCurve = ql.TradingTimeYieldTermStructure(usd, tt)
        for d in (ql.Date(5, 1, 2024), ql.Date(8, 1, 2024), ql.Date(2, 7, 2024)):
            self.assertAlmostEqual(ttCurve.discount(d), usd.discount(d), places=14)
        dc = ql.TradingTimeDayCounter(tt)
        self.assertAlmostEqual(dc.yearFraction(TODAY, ql.Date(8, 1, 2024)), tt.tradingTime(ql.Date(8, 1, 2024)),
                               places=14)


class FxPairMarketTest(unittest.TestCase):

    def setUp(self):
        # the markets are fixed-date; options priced on them need the evaluation date
        ql.Settings.instance().evaluationDate = TODAY

    def tearDown(self):
        ql.Settings.instance().evaluationDate = ql.Date()

    def testEachPairBuildsItsSurface(self):
        """EURUSD and GBPUSD (pips deltas) and USDJPY (premium-adjusted): pillars, forwards and fitted smiles."""
        settlement = ql.FxSettleConvention(ql.WeekendsOnly(), 2)
        for pair, (_, _, spot, rFor, rDom, deltaType) in PAIRS.items():
            with self.subTest(pair=pair):
                m = market(pair)
                self.assertEqual(m.conventions().name(), pair)
                self.assertEqual(list(m.pillars()), list(ql.fxExpiryDates(TODAY, TENORS, settlement)))
                surface = m.volSurface()
                self.assertEqual(surface.smileModel(), ql.FxSmileModel.Sabr)
                self.assertEqual(len(surface.pillarSmileSections()), len(TENORS))
                for i, expiry in enumerate(m.pillars()):
                    section = surface.pillarSmileSection(i)
                    self.assertEqual(section.premiumAdjust(), deltaType == ql.DeltaVolQuote.PaSpot)
                    # the forward from spot date to delivery, the section's too
                    dFor, dDom = m.settlementDiscounts(expiry)
                    self.assertAlmostEqual(m.forward(expiry), spot * dFor / dDom, delta=1e-12 * spot)
                    self.assertAlmostEqual(section.forward(), m.forward(expiry), delta=1e-12 * spot)
                    # SABR (beta = 1) has 3 parameters for 5 quotes: on these quotes it fits
                    # to 7-14bp RMS, missing the 25D butterfly by up to 30bp; limits just above
                    self.assertLess(section.calibrationError(), 15e-4)
                    q = m.expiryQuotes(expiry)
                    self.assertAlmostEqual(q.atm, ATMS[i], delta=15e-4)
                    for j in range(len(DELTAS)):
                        self.assertAlmostEqual(q.riskReversals[j], RRS[i][j], delta=10e-4)
                        self.assertAlmostEqual(q.butterflies[j], BFS[i][j], delta=35e-4)

    def testSurfaceReproducesItsPillarSmiles(self):
        """At each pillar the surface's vols and quotes are those of the pillar's calibrated smile."""
        for pair in PAIRS:
            for model in (ql.FxSmileModel.Sabr, ql.FxSmileModel.Polynomial):
                m = market(pair, ql.FxVolSurfaceConfig(model))
                surface = m.volSurface()
                for i, expiry in enumerate(m.pillars()):
                    with self.subTest(pair=pair, model=model, pillar=i):
                        section = surface.pillarSmileSection(i)
                        self.assertAlmostEqual(m.expiryQuotes(expiry).atm, section.atmVol(), delta=1e-10)
                        for moneyness in (0.9, 1.0, 1.1):
                            k = moneyness * section.forward()
                            self.assertAlmostEqual(m.marketVol(expiry, k), section.volByStrike(k), delta=1e-10)

    @unittest.expectedFailure
    def testCostFlatDynamicsCalibratesShortTenors(self):
        """Known failure of the C++: on these quotes the flat-dynamics cost model doesn't calibrate
        at the 1W and 1M pillars ("root not bracketed"); SABR and polynomial do."""
        m = market("EURUSD", ql.FxVolSurfaceConfig(ql.FxSmileModel.CostFlatDynamics))
        for section in m.volSurface().pillarSmileSections():
            self.assertLess(section.calibrationError(), 50e-4)

    def testBlackProcessPricesAtMarketVols(self):
        """As testFxPairMarketTradingTimePreservesPrices: the trading-time Black process reprices calendar-time Black."""
        m = market("EURUSD")
        process = m.blackProcess()
        for expiry in (ql.Date(9, 1, 2024), ql.Date(1, 2, 2024), ql.Date(2, 5, 2024)):
            fwd = m.forward(expiry)
            for moneyness in (0.95, 1.0, 1.05):
                k = moneyness * fwd
                option = ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Call, k), ql.EuropeanExercise(expiry))
                option.setPricingEngine(ql.AnalyticEuropeanEngine(process))
                stdDev = m.marketVol(expiry, k) * math.sqrt(ql.Actual365Fixed().yearFraction(m.asOf(), expiry))
                black = ql.blackFormula(ql.Option.Call, k, fwd, stdDev, m.domesticCurve().discount(expiry))
                self.assertAlmostEqual(option.NPV(), black, delta=1e-10 * black + 1e-14)

    def testLocalVolProcess(self):
        m = market("EURUSD")
        process = m.localVolProcess()
        expiry = ql.Date(2, 4, 2024)
        k = m.forward(expiry)
        option = ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Call, k), ql.EuropeanExercise(expiry))
        option.setPricingEngine(ql.FdBlackScholesVanillaEngine(process, 100, 100, 0, ql.FdmSchemeDesc.Douglas(), True))
        stdDev = m.marketVol(expiry, k) * math.sqrt(ql.Actual365Fixed().yearFraction(m.asOf(), expiry))
        black = ql.blackFormula(ql.Option.Call, k, k, stdDev, m.domesticCurve().discount(expiry))
        self.assertAlmostEqual(option.NPV(), black, delta=0.005 * black)

    def testOtherModelsAndInterpolation(self):
        for model, interpolation in ((ql.FxSmileModel.CostStickyDelta, ql.FxVolInterpolation.Ncp),
                                     (ql.FxSmileModel.Svi, ql.FxVolInterpolation.Clark)):
            with self.subTest(model=model, interpolation=interpolation):
                m = market("USDJPY", ql.FxVolSurfaceConfig(model, interpolation, 0.2))
                self.assertEqual(m.config().model, model)
                self.assertEqual(m.volSurface().smileModel(), model)
                expiry = ql.Date(2, 5, 2024)  # between pillars
                self.assertGreater(m.marketVol(expiry, m.forward(expiry)), 0.0)
        sticky = market("USDJPY", ql.FxVolSurfaceConfig(ql.FxSmileModel.CostStickyDelta))
        section = ql.as_fx_cost_smile_section_sticky_delta(sticky.volSurface().pillarSmileSection(2))
        self.assertIsNotNone(section)
        self.assertEqual(len(section.costs()), 4)

    def testSurfaceInBlackVolHandle(self):
        m = market("EURUSD")
        handle = ql.BlackVolTermStructureHandle(m.volSurface())
        self.assertEqual(handle.referenceDate(), TODAY)
        self.assertGreater(handle.blackVol(0.25, m.spot()), 0.0)

    def testMarketsAreImmutable(self):
        m = market("GBPUSD")
        bumped = m.withSpot(1.30)
        self.assertEqual(m.spot(), 1.27)
        self.assertEqual(bumped.spot(), 1.30)
        q = m.quotes()
        higher = m.withQuotes(ql.FxVolQuotes(q.tenors, q.deltas, [a + 0.01 for a in q.atms], q.riskReversals,
                                             q.butterflies))
        expiry = m.pillars()[2]
        self.assertAlmostEqual(higher.expiryQuotes(expiry).atm - m.expiryQuotes(expiry).atm, 0.01, delta=1e-3)
        self.assertEqual(list(m.quotes().atms), ATMS)

    def testEventsRaiseVarianceAfterTheirDate(self):
        m = market("EURUSD")
        event = ql.FxVolEvent(ql.Date(31, 1, 2024), 0.8, 1.5e-5)
        self.assertEqual(event.variance, 1.5e-5)
        withEvent = m.withEvents([event])
        self.assertEqual(len(withEvent.events()), 1)
        cut = m.conventions().cut()
        self.assertEqual(ql.fxEventVariance([event], TODAY, ql.Date(1, 2, 2024), cut), 1.5e-5)
        self.assertEqual(ql.fxEventVariance([event], TODAY, ql.Date(30, 1, 2024), cut), 0.0)
        self.assertTrue(ql.fxEventPrecedesExpiry(event, ql.Date(1, 2, 2024), cut))
        self.assertEqual(len(ql.fxPendingEvents([event], ql.Date(1, 2, 2024))), 0)

        def totalVariance(mkt, d):
            k = mkt.forward(d)
            return mkt.marketVol(d, k) ** 2 * ql.Actual365Fixed().yearFraction(TODAY, d)

        before, after = ql.Date(30, 1, 2024), ql.Date(1, 2, 2024)
        jumpWith = totalVariance(withEvent, after) - totalVariance(withEvent, before)
        jumpWithout = totalVariance(m, after) - totalVariance(m, before)
        self.assertGreater(jumpWith, jumpWithout + 0.5 * 1.5e-5)

    def testRolledMarketKeepsForwards(self):
        m = market("USDJPY")
        friday = ql.Date(5, 1, 2024)
        rolled = m.rolled(friday)
        self.assertEqual(rolled.asOf(), friday)
        for expiry in (ql.Date(1, 2, 2024), ql.Date(2, 7, 2024)):
            self.assertAlmostEqual(rolled.forward(expiry), m.forward(expiry), delta=1e-10 * m.spot())

    def testSmileSectionFromExpiryQuotes(self):
        m = market("EURUSD")
        expiry = ql.Date(2, 5, 2024)
        q = ql.FxExpiryQuotes(0.088, [-0.015, -0.03], [0.0047, 0.01])
        section = m.smileSection(expiry, q)
        self.assertAlmostEqual(section.forward(), m.forward(expiry), delta=1e-12 * m.spot())
        self.assertAlmostEqual(section.atmVol(), 0.088, delta=1e-3)

    def testTradingTimeMarket(self):
        m = market("EURUSD")
        tt = m.tradingTime()
        self.assertAlmostEqual(m.tradingTimeDayCounter().yearFraction(TODAY, ql.Date(8, 1, 2024)),
                               tt.tradingTime(ql.Date(8, 1, 2024)), places=14)
        d = ql.Date(2, 7, 2024)
        self.assertAlmostEqual(m.tradingTimeDomesticCurve().discount(d), m.domesticCurve().discount(d), places=14)


if __name__ == "__main__":
    print("testing QuantLib", ql.__version__)
    unittest.main(verbosity=2)
