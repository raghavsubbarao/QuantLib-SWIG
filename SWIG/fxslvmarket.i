/*
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
*/

/* FX pair market and vol surface of the custom QuantLib build
   (ql/experimental/fxslv/): pair conventions, expiry cut and tenor dates,
   vol events, the trading-time clock, the variance surfaces and FxPairMarket.
*/

#ifndef quantlib_fxslv_market_i
#define quantlib_fxslv_market_i

%include fxslv.i
%include stochasticprocess.i
%include null.i

%{
#include <ql/experimental/fxslv/conventions/fxexpirycut.hpp>
#include <ql/experimental/fxslv/conventions/fxpairconventions.hpp>
#include <ql/experimental/fxslv/conventions/fxtenorexpiry.hpp>
#include <ql/experimental/fxslv/tradingtime/tradingtimetermstructure.hpp>
#include <ql/experimental/fxslv/tradingtime/tradingtimedaycounter.hpp>
#include <ql/experimental/fxslv/tradingtime/tradingtimeyieldtermstructure.hpp>
#include <ql/experimental/fxslv/fxeventvariance.hpp>
#include <ql/experimental/fxslv/fxvariancesurface.hpp>
#include <ql/experimental/fxslv/fxvolsurfacebuilder.hpp>
#include <ql/experimental/fxslv/fxpairmarket.hpp>

using QuantLib::FxExpiryCut;
using QuantLib::FxPairConventions;
using QuantLib::fxDeliveryDate;
using QuantLib::fxExpiryDate;
using QuantLib::fxExpiryDates;
using QuantLib::TradingTimeEvent;
using QuantLib::JumpTradingTimeEvent;
using QuantLib::DiffuseTradingTimeEvent;
using QuantLib::TradingTimeTermStructure;
using QuantLib::TradingTimeDayCounter;
using QuantLib::TradingTimeYieldTermStructure;
using QuantLib::FxVolEvent;
using QuantLib::fxPendingEvents;
using QuantLib::fxEventPrecedesExpiry;
using QuantLib::fxEventVariance;
using QuantLib::makeFxEventTradingTime;
using QuantLib::FxVarianceSurface;
using QuantLib::FxVarianceSurfaceClark;
using QuantLib::FxVarianceSurfaceNCP;
using QuantLib::FxVolInterpolation;
using QuantLib::FxVolSurfaceConfig;
using QuantLib::FxVolQuotes;
using QuantLib::checkFxVolQuotes;
using QuantLib::makeFxVolSurface;
using QuantLib::FxExpiryQuotes;
using QuantLib::FxPairMarket;
%}


// ---------------------------------------------------------------------------
// Conventions
// ---------------------------------------------------------------------------

class FxExpiryCut {
  public:
    explicit FxExpiryCut(Natural hour, Natural minute = 0);
    Real timeOfDay() const;
    bool precedes(const Date& date, Real timeOfDay, const Date& expiry) const;
};

class FxPairConventions {
  public:
    FxPairConventions(std::string foreignCurrency,
                      std::string domesticCurrency,
                      FxSettleConvention settlement,
                      FxExpiryCut cut,
                      DeltaVolQuote::DeltaType deltaType,
                      DeltaVolQuote::AtmType atmType,
                      FxRrBfQuotes::FlyType flyType);
    const std::string& foreignCurrency() const;
    const std::string& domesticCurrency() const;
    std::string name() const;
    const FxSettleConvention& settlement() const;
    const FxExpiryCut& cut() const;
    DeltaVolQuote::DeltaType deltaType() const;
    DeltaVolQuote::AtmType atmType() const;
    FxRrBfQuotes::FlyType flyType() const;
    FxPairConventions withFlyType(FxRrBfQuotes::FlyType flyType) const;
};

Date fxDeliveryDate(const Date& tradeDate, const Period& tenor, const FxSettleConvention& settlement);
Date fxExpiryDate(const Date& tradeDate, const Period& tenor, const FxSettleConvention& settlement);
std::vector<Date> fxExpiryDates(const Date& tradeDate,
                                const std::vector<Period>& tenors,
                                const FxSettleConvention& settlement);


// ---------------------------------------------------------------------------
// Trading time
// ---------------------------------------------------------------------------

%shared_ptr(TradingTimeEvent)
class TradingTimeEvent {
  private:
    TradingTimeEvent();
  public:
    Real start() const;
    Real end() const;
    const Handle<Quote>& weight() const;
    Real released(Real day) const;
    Real releaseRate(Real day) const;
    bool allowsNegativeWeight() const;
};

%shared_ptr(JumpTradingTimeEvent)
class JumpTradingTimeEvent : public TradingTimeEvent {
  public:
    JumpTradingTimeEvent(const Date& date, Real timeOfDay, Handle<Quote> weight);
};

%shared_ptr(DiffuseTradingTimeEvent)
class DiffuseTradingTimeEvent : public TradingTimeEvent {
  public:
    DiffuseTradingTimeEvent(const Date& startDate,
                            Real startTimeOfDay,
                            const Date& endDate,
                            Real endTimeOfDay,
                            Handle<Quote> weight);
};

#if defined(SWIGCSHARP)
SWIG_STD_VECTOR_ENHANCED( ext::shared_ptr<TradingTimeEvent> )
#endif
%template(TradingTimeEventVector) std::vector<ext::shared_ptr<TradingTimeEvent> >;

%shared_ptr(TradingTimeTermStructure)
class TradingTimeTermStructure : public TermStructure {
  public:
    TradingTimeTermStructure(const Date& referenceDate,
                             Calendar calendar = WeekendsOnly(),
                             Real holidayWeight = 0.2,
                             std::vector<ext::shared_ptr<TradingTimeEvent> > events = std::vector<ext::shared_ptr<TradingTimeEvent> >());
    Time tradingTime(const Date& d1, const Date& d2) const;
    Time tradingTime(const Date& d) const;
    Time tradingTime(Time t) const;
    Time calendarTime(Time tradingTime) const;
    Real holidayWeight() const;
    const std::vector<ext::shared_ptr<TradingTimeEvent> >& events() const;
    std::vector<std::pair<Time, Time> > eventIntervals() const;
};

%template(TradingTimeTermStructureHandle) Handle<TradingTimeTermStructure>;
%template(RelinkableTradingTimeTermStructureHandle) RelinkableHandle<TradingTimeTermStructure>;

class TradingTimeDayCounter : public DayCounter {
  public:
    explicit TradingTimeDayCounter(const Handle<TradingTimeTermStructure>& tradingTime);
};

%shared_ptr(TradingTimeYieldTermStructure)
class TradingTimeYieldTermStructure : public YieldTermStructure {
  public:
    TradingTimeYieldTermStructure(Handle<YieldTermStructure> curve,
                                  Handle<TradingTimeTermStructure> tradingTime);
    const Handle<YieldTermStructure>& calendarTimeCurve() const;
    const Handle<TradingTimeTermStructure>& tradingTime() const;
};


// ---------------------------------------------------------------------------
// Vol events
// ---------------------------------------------------------------------------

struct FxVolEvent {
    Date date;
    Real timeOfDay;
    Real variance;
    %extend {
        //! An event releasing ATM total variance at a time of day (New York clock) on a date.
        FxVolEvent(const Date& date, Real timeOfDay, Real variance) {
            return new FxVolEvent{date, timeOfDay, variance};
        }
    }
};

%template(FxVolEventVector) std::vector<FxVolEvent>;

std::vector<FxVolEvent> fxPendingEvents(const std::vector<FxVolEvent>& events,
                                        const Date& valuationDate);
bool fxEventPrecedesExpiry(const FxVolEvent& event, const Date& expiry, const FxExpiryCut& cut);
Real fxEventVariance(const std::vector<FxVolEvent>& events,
                     const Date& valuationDate,
                     const Date& expiry,
                     const FxExpiryCut& cut);
ext::shared_ptr<TradingTimeTermStructure>
makeFxEventTradingTime(const Date& referenceDate,
                       const std::vector<Date>& pillars,
                       const std::vector<Volatility>& atmVols,
                       const std::vector<FxVolEvent>& events,
                       const FxExpiryCut& cut,
                       const Calendar& calendar,
                       Real holidayWeight);


// ---------------------------------------------------------------------------
// Variance surfaces
// ---------------------------------------------------------------------------

#if defined(SWIGCSHARP)
SWIG_STD_VECTOR_ENHANCED( ext::shared_ptr<FxSmileSection> )
#endif
%template(FxSmileSectionVector) std::vector<ext::shared_ptr<FxSmileSection> >;

%define FX_VARIANCE_SURFACE_CONSTRUCTOR(Name)
    Name(FxSmileModel model,
         const Date& referenceDate,
         const Handle<Quote>& spot,
         const std::vector<Date>& pillars,
         const std::vector<Handle<Quote> >& atms,
         const std::vector<std::vector<Handle<Quote> > >& rrs,
         const std::vector<std::vector<Handle<Quote> > >& bfs,
         const std::vector<Real>& deltas,
         const Handle<YieldTermStructure>& forTs,
         const Handle<YieldTermStructure>& domTs,
         const Handle<TradingTimeTermStructure>& timesTs,
         DeltaVolQuote::DeltaType deltaType,
         DeltaVolQuote::AtmType atmType,
         FxRrBfQuotes::FlyType flyType,
         const FxSettleConvention& settlement,
         const FxExpiryCut& cut,
         const Calendar& cal = WeekendsOnly(),
         BusinessDayConvention bdc = Following,
         bool forceMonotoneVariance = true,
         Time nodeSpacing = 1.0 / 365);
%enddef

/* In C++ the surfaces derive from BlackVarianceTermStructure, which the
   wrappers don't declare; BlackVolTermStructure is the declared base, so a
   surface can be put in a BlackVolTermStructureHandle. */
%shared_ptr(FxVarianceSurface)
class FxVarianceSurface : public BlackVolTermStructure {
  private:
    FxVarianceSurface();
  public:
    Real atmVar(Date d) const;
    Real atmVol(Date d) const;
    Real fwd(const Date& expiry) const;
    Real fwd(Time t) const;
    FxSmileModel smileModel() const;
    Handle<Quote> spot() const;
    const std::vector<ext::shared_ptr<FxSmileSection> >& pillarSmileSections() const;
    const std::vector<Date>& pillarDates() const;
    ext::shared_ptr<FxSmileSection> pillarSmileSection(Size pillar) const;
    const FxSettleConvention& settlement() const;
    const FxExpiryCut& expiryCut() const;
    Volatility marketVol(const Date& expiry, Real strike) const;
    const Handle<TradingTimeTermStructure>& tradingTimeStructure() const;
    Handle<YieldTermStructure> domesticDiscountCurve() const;
    Handle<YieldTermStructure> foreignDiscountCurve() const;
};

%shared_ptr(FxVarianceSurfaceClark)
class FxVarianceSurfaceClark : public FxVarianceSurface {
  public:
    FX_VARIANCE_SURFACE_CONSTRUCTOR(FxVarianceSurfaceClark)
};

%shared_ptr(FxVarianceSurfaceNCP)
class FxVarianceSurfaceNCP : public FxVarianceSurface {
  public:
    FX_VARIANCE_SURFACE_CONSTRUCTOR(FxVarianceSurfaceNCP)
};


// ---------------------------------------------------------------------------
// Quotes, configuration and the surface builder
// ---------------------------------------------------------------------------

enum class FxVolInterpolation { Ncp, Clark };

#if defined(SWIGPYTHON)
%pythoncode %{
class FxVolInterpolation:
    """How a surface interpolates smiles between pillars (C++ enum class FxVolInterpolation)."""
    Ncp = FxVolInterpolation_Ncp
    Clark = FxVolInterpolation_Clark
%}
#endif

struct FxVolSurfaceConfig {
    explicit FxVolSurfaceConfig(FxSmileModel model = FxSmileModel::Sabr,
                                FxVolInterpolation interpolation = FxVolInterpolation::Ncp,
                                Real holidayWeight = 0.2);
    FxSmileModel model;
    FxVolInterpolation interpolation;
    Real holidayWeight;
};

struct FxVolQuotes {
    FxVolQuotes();
    FxVolQuotes(std::vector<Period> tenors,
                std::vector<Real> deltas,
                std::vector<Volatility> atms,
                std::vector<std::vector<Volatility> > riskReversals,
                std::vector<std::vector<Volatility> > butterflies);
    std::vector<Period> tenors;
    std::vector<Real> deltas;
    std::vector<Volatility> atms;
    std::vector<std::vector<Volatility> > riskReversals;
    std::vector<std::vector<Volatility> > butterflies;
};

void checkFxVolQuotes(const FxVolQuotes& quotes, const std::string& pair);

ext::shared_ptr<FxVarianceSurface>
makeFxVolSurface(const Date& asOf,
                 const FxPairConventions& conventions,
                 const Handle<Quote>& spot,
                 const FxVolQuotes& quotes,
                 const Handle<YieldTermStructure>& foreignCurve,
                 const Handle<YieldTermStructure>& domesticCurve,
                 const std::vector<FxVolEvent>& events,
                 const FxVolSurfaceConfig& config);


// ---------------------------------------------------------------------------
// The market of a pair
// ---------------------------------------------------------------------------

struct FxExpiryQuotes {
    Volatility atm;
    std::vector<Volatility> riskReversals;
    std::vector<Volatility> butterflies;
    %extend {
        FxExpiryQuotes(Volatility atm,
                       const std::vector<Volatility>& riskReversals,
                       const std::vector<Volatility>& butterflies) {
            return new FxExpiryQuotes{atm, riskReversals, butterflies};
        }
    }
};

class FxPairMarket {
  public:
    FxPairMarket(const Date& asOf,
                 FxPairConventions conventions,
                 Real spot,
                 Handle<YieldTermStructure> foreignCurve,
                 Handle<YieldTermStructure> domesticCurve,
                 FxVolQuotes quotes,
                 std::vector<FxVolEvent> events = std::vector<FxVolEvent>(),
                 FxVolSurfaceConfig config = FxVolSurfaceConfig());

    // market data
    const Date& asOf() const;
    const FxPairConventions& conventions() const;
    Real spot() const;
    const Handle<Quote>& spotQuote() const;
    const Handle<YieldTermStructure>& foreignCurve() const;
    const Handle<YieldTermStructure>& domesticCurve() const;
    const FxVolQuotes& quotes() const;
    const std::vector<FxVolEvent>& events() const;
    const FxVolSurfaceConfig& config() const;
    const std::vector<Date>& pillars() const;

    // forwards
    std::pair<DiscountFactor, DiscountFactor> settlementDiscounts(const Date& expiry) const;
    Real forward(const Date& expiry) const;

    // vols
    const ext::shared_ptr<FxVarianceSurface>& volSurface() const;
    Volatility marketVol(const Date& expiry, Real strike) const;
    ext::shared_ptr<FxSmileSection> smileSection(const Date& expiry, const FxExpiryQuotes& quotes) const;
    FxExpiryQuotes expiryQuotes(const Date& expiry) const;

    // the market on the trading-time clock
    const Handle<TradingTimeTermStructure>& tradingTime() const;
    DayCounter tradingTimeDayCounter() const;
    const Handle<YieldTermStructure>& tradingTimeDomesticCurve() const;
    const Handle<YieldTermStructure>& tradingTimeForeignCurve() const;
    ext::shared_ptr<GeneralizedBlackScholesProcess> blackProcess() const;
    ext::shared_ptr<GeneralizedBlackScholesProcess>
    localVolProcess(doubleOrNull fallback = Null<Real>()) const;

    // other markets
    FxPairMarket withSpot(Real spot) const;
    FxPairMarket withCurves(Handle<YieldTermStructure> foreignCurve,
                            Handle<YieldTermStructure> domesticCurve) const;
    FxPairMarket withQuotes(FxVolQuotes quotes) const;
    FxPairMarket withEvents(std::vector<FxVolEvent> events) const;
    FxPairMarket smileStrangles() const;
    FxPairMarket rolled(const Date& next) const;
};

#endif
