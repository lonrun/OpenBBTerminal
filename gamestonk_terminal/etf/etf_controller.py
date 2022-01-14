"""ETF Controller"""
__docformat__ = "numpy"

import argparse
import os
from datetime import datetime, timedelta
from typing import List
import yfinance as yf
import matplotlib.pyplot as plt
import mplfinance as mpf
from colorama import Style

from prompt_toolkit.completion import NestedCompleter

from thepassiveinvestor import create_ETF_report

from gamestonk_terminal.parent_classes import BaseController
from gamestonk_terminal import feature_flags as gtff
from gamestonk_terminal.etf import (
    stockanalysis_view,
    financedatabase_view,
    stockanalysis_model,
    yfinance_view,
)
from gamestonk_terminal.common import newsapi_view
from gamestonk_terminal.helper_funcs import (
    EXPORT_BOTH_RAW_DATA_AND_FIGURES,
    EXPORT_ONLY_RAW_DATA_ALLOWED,
    check_non_negative_float,
    check_positive,
    valid_date,
    parse_known_args_and_warn,
    plot_autoscale,
    export_data,
)
from gamestonk_terminal.menu import session
from gamestonk_terminal.stocks import stocks_helper
from gamestonk_terminal.etf.technical_analysis import ta_controller
from gamestonk_terminal.stocks.comparison_analysis import ca_controller
from gamestonk_terminal.etf.screener import screener_controller
from gamestonk_terminal.etf.discovery import disc_controller

# pylint: disable=C0415,C0302


class ETFController(BaseController):
    """ETF Controller class"""

    CHOICES_COMMANDS = [
        "ln",
        "ld",
        "load",
        "overview",
        "holdings",
        "news",
        "candle",
        "pir",
        "weights",
        "summary",
        "compare",
    ]
    CHOICES_MENUS = [
        "ta",
        "pred",
        "ca",
        "scr",
        "disc",
    ]

    def __init__(self, queue: List[str] = None):
        """Constructor"""
        super().__init__("/etf/", queue)

        self.etf_name = ""
        self.etf_data = ""
        self.etf_holdings: List = list()

        if session and gtff.USE_PROMPT_TOOLKIT:
            choices: dict = {c: {} for c in self.controller_choices}
            self.completer = NestedCompleter.from_nested_dict(choices)

    def print_help(self):
        """Print help"""
        help_txt = f"""
    ln            lookup by name [FinanceDatabase/StockAnalysis.com]
    ld            lookup by description [FinanceDatabase]
    load          load ETF data [Yfinance]
{Style.DIM if not self.etf_name else ""}
Symbol: {self.etf_name}{Style.DIM if len(self.etf_holdings)==0 else ""}
Major holdings: {', '.join(self.etf_holdings)}

>   ca            comparison analysis,          e.g.: get similar, historical, correlation, financials
{Style.RESET_ALL}
>   disc          discover ETFs,                e.g.: gainers/decliners/active
>   scr           screener ETFs,                e.g.: overview/performance, using preset filters
{Style.DIM if not self.etf_name else ""}
    overview      get overview [StockAnalysis]
    holdings      top company holdings [StockAnalysis]
    weights       sector weights allocation [Yfinance]
    summary       summary description of the ETF [Yfinance]
    candle        view a candle chart for ETF
    news          latest news of the company [News API]

    pir           create (multiple) passive investor excel report(s) [PassiveInvestor]
    compare       compare multiple different ETFs [StockAnalysis]

>   ta            technical analysis,           e.g.: ema, macd, rsi, adx, bbands, obv
>   pred          prediction techniques,        e.g.: regression, arima, rnn, lstm
{Style.RESET_ALL}"""
        print(help_txt)

    def custom_reset(self):
        """Class specific component of reset command"""
        if self.etf_name:
            return ["etf", f"load {self.etf_name}"]
        return []

    def call_ln(self, other_args: List[str]):
        """Process ln command"""
        parser = argparse.ArgumentParser(
            add_help=False,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog="ln",
            description="Lookup by name [Source: FinanceDatabase/StockAnalysis.com]",
        )
        parser.add_argument(
            "-n",
            "--name",
            type=str,
            dest="name",
            nargs="+",
            help="Name to look for ETFs",
            required="-h" not in other_args,
        )
        parser.add_argument(
            "-s",
            "--source",
            type=str,
            default="fd",
            dest="source",
            help="Name to search for, using either FinanceDatabase (fd) or StockAnalysis (sa) as source.",
            choices=["sa", "fd"],
        )
        parser.add_argument(
            "-l",
            "--limit",
            type=check_positive,
            dest="limit",
            help="Limit of ETFs to display",
            default=5,
        )

        if other_args and "-" not in other_args[0][0]:
            other_args.insert(0, "-n")

        ns_parser = parse_known_args_and_warn(
            parser, other_args, export_allowed=EXPORT_ONLY_RAW_DATA_ALLOWED
        )
        if ns_parser:
            name_to_search = " ".join(ns_parser.name)
            if ns_parser.source == "fd":
                financedatabase_view.display_etf_by_name(
                    name=name_to_search,
                    limit=ns_parser.limit,
                    export=ns_parser.export,
                )
            elif ns_parser.source == "sa":
                stockanalysis_view.display_etf_by_name(
                    name=name_to_search,
                    limit=ns_parser.limit,
                    export=ns_parser.export,
                )
            else:
                print("Wrong source choice!\n")

    def call_ld(self, other_args: List[str]):
        """Process ld command"""
        parser = argparse.ArgumentParser(
            add_help=False,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog="ld",
            description="Lookup by description [Source: FinanceDatabase/StockAnalysis.com]",
        )
        parser.add_argument(
            "-d",
            "--description",
            type=str,
            dest="description",
            nargs="+",
            help="Name to look for ETFs",
            required="-h" not in other_args,
        )
        parser.add_argument(
            "-l",
            "--limit",
            type=check_positive,
            dest="limit",
            help="Limit of ETFs to display",
            default=5,
        )

        if other_args and "-" not in other_args[0][0]:
            other_args.insert(0, "-d")

        ns_parser = parse_known_args_and_warn(
            parser, other_args, export_allowed=EXPORT_ONLY_RAW_DATA_ALLOWED
        )
        if ns_parser:
            description_to_search = " ".join(ns_parser.description)
            financedatabase_view.display_etf_by_description(
                description=description_to_search,
                limit=ns_parser.limit,
                export=ns_parser.export,
            )

    def call_load(self, other_args: List[str]):
        """Process load command"""
        parser = argparse.ArgumentParser(
            add_help=False,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog="load",
            description="Load ETF ticker to perform analysis on.",
        )
        parser.add_argument(
            "-t",
            "--ticker",
            action="store",
            dest="ticker",
            required="-h" not in other_args,
            help="ETF ticker",
        )
        parser.add_argument(
            "-s",
            "--start",
            type=valid_date,
            default=(datetime.now() - timedelta(days=366)).strftime("%Y-%m-%d"),
            dest="start",
            help="The starting date (format YYYY-MM-DD) of the ETF",
        )
        parser.add_argument(
            "-e",
            "--end",
            type=valid_date,
            default=datetime.now().strftime("%Y-%m-%d"),
            dest="end",
            help="The ending date (format YYYY-MM-DD) of the ETF",
        )
        parser.add_argument(
            "-l",
            "--limit",
            type=check_positive,
            default=5,
            dest="limit",
            help="Limit of holdings to display",
        )
        if other_args and "-" not in other_args[0][0]:
            other_args.insert(0, "-t")

        ns_parser = parse_known_args_and_warn(parser, other_args)
        if ns_parser:
            df_etf_candidate = yf.download(
                ns_parser.ticker,
                start=ns_parser.start,
                end=ns_parser.end,
                progress=False,
            )
            if df_etf_candidate.empty:
                print("ETF ticker provided does not exist!\n")
                return

            df_etf_candidate.index.name = "date"

            self.etf_name = ns_parser.ticker.upper()
            self.etf_data = df_etf_candidate

            holdings = stockanalysis_model.get_etf_holdings(self.etf_name)
            if holdings.empty:
                print("No company holdings found!\n")
            else:
                self.etf_holdings = holdings.index[: ns_parser.limit].tolist()
                print(f"Top company holdings found: {', '.join(self.etf_holdings)}\n")

            print("")

    def call_overview(self, other_args: List[str]):
        """Process overview command"""
        parser = argparse.ArgumentParser(
            add_help=False,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog="overview",
            description="Get overview data for selected etf",
        )
        ns_parser = parse_known_args_and_warn(
            parser, other_args, export_allowed=EXPORT_ONLY_RAW_DATA_ALLOWED
        )

        if ns_parser:
            stockanalysis_view.view_overview(
                symbol=self.etf_name, export=ns_parser.export
            )

    def call_holdings(self, other_args: List[str]):
        """Process holdings command"""
        parser = argparse.ArgumentParser(
            add_help=False,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog="holdings",
            description="Look at ETF company holdings",
        )
        parser.add_argument(
            "-l",
            "--limit",
            type=int,
            dest="limit",
            help="Number of holdings to get",
            default=10,
        )
        if other_args and "-" not in other_args[0][0]:
            other_args.insert(0, "-l")

        ns_parser = parse_known_args_and_warn(
            parser, other_args, export_allowed=EXPORT_ONLY_RAW_DATA_ALLOWED
        )
        if ns_parser:
            stockanalysis_view.view_holdings(
                symbol=self.etf_name,
                num_to_show=ns_parser.limit,
                export=ns_parser.export,
            )

    def call_news(self, other_args: List[str]):
        """Process news command"""
        parser = argparse.ArgumentParser(
            add_help=False,
            prog="news",
            description="""
                Prints latest news about ETF, including date, title and web link. [Source: News API]
            """,
        )
        parser.add_argument(
            "-l",
            "--limit",
            action="store",
            dest="limit",
            type=check_positive,
            default=5,
            help="Limit of latest news being printed.",
        )
        parser.add_argument(
            "-d",
            "--date",
            action="store",
            dest="n_start_date",
            type=valid_date,
            default=datetime.now() - timedelta(days=7),
            help="The starting date (format YYYY-MM-DD) to search articles from",
        )
        parser.add_argument(
            "-o",
            "--oldest",
            action="store_false",
            dest="n_oldest",
            default=True,
            help="Show oldest articles first",
        )
        parser.add_argument(
            "-s",
            "--sources",
            default=[],
            nargs="+",
            help="Show news only from the sources specified (e.g bbc yahoo.com)",
        )
        if other_args and "-" not in other_args[0][0]:
            other_args.insert(0, "-l")
        ns_parser = parse_known_args_and_warn(parser, other_args)
        if ns_parser:
            if self.etf_name:
                sources = ns_parser.sources
                for idx, source in enumerate(sources):
                    if source.find(".") == -1:
                        sources[idx] += ".com"

                d_stock = yf.Ticker(self.etf_name).info

                newsapi_view.news(
                    term=d_stock["shortName"].replace(" ", "+")
                    if "shortName" in d_stock
                    else self.etf_name,
                    num=ns_parser.limit,
                    s_from=ns_parser.n_start_date.strftime("%Y-%m-%d"),
                    show_newest=ns_parser.n_oldest,
                    sources=",".join(sources),
                )
            else:
                print("Use 'load <ticker>' prior to this command!", "\n")

    def call_candle(self, other_args: List[str]):
        """Process candle command"""
        parser = argparse.ArgumentParser(
            add_help=False,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog="candle",
            description="Shows historic data for an ETF",
        )
        ns_parser = parse_known_args_and_warn(
            parser, other_args, EXPORT_BOTH_RAW_DATA_AND_FIGURES
        )
        if ns_parser:
            if self.etf_name:
                data = stocks_helper.process_candle(self.etf_data)
                df_etf = stocks_helper.find_trendline(data, "OC_High", "high")
                df_etf = stocks_helper.find_trendline(data, "OC_Low", "low")

                mc = mpf.make_marketcolors(
                    up="green",
                    down="red",
                    edge="black",
                    wick="black",
                    volume="in",
                    ohlc="i",
                )

                s = mpf.make_mpf_style(marketcolors=mc, gridstyle=":", y_on_right=True)

                ap0 = []

                if "OC_High_trend" in df_etf.columns:
                    ap0.append(
                        mpf.make_addplot(df_etf["OC_High_trend"], color="g"),
                    )

                if "OC_Low_trend" in df_etf.columns:
                    ap0.append(
                        mpf.make_addplot(df_etf["OC_Low_trend"], color="b"),
                    )

                if gtff.USE_ION:
                    plt.ion()

                mpf.plot(
                    df_etf,
                    type="candle",
                    mav=(20, 50),
                    volume=True,
                    title=f"\nETF: {self.etf_name}",
                    addplot=ap0,
                    xrotation=10,
                    style=s,
                    figratio=(10, 7),
                    figscale=1.10,
                    figsize=(plot_autoscale()),
                    update_width_config=dict(
                        candle_linewidth=1.0, candle_width=0.8, volume_linewidth=1.0
                    ),
                )
                print("")

                export_data(
                    ns_parser.export,
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "candle"),
                    f"{self.etf_name}",
                    self.etf_data,
                )

            else:
                print("No ticker loaded. First use `load {ticker}`\n")

    def call_pir(self, other_args):
        """Process pir command"""
        parser = argparse.ArgumentParser(
            add_help=False,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog="pir",
            description="Create passive investor ETF excel report",
        )
        parser.add_argument(
            "-e",
            "--etfs",
            type=str,
            dest="names",
            help="Symbols to create a report for (e.g. ARKW,ARKQ)",
            default=self.etf_name,
        )
        parser.add_argument(
            "--filename",
            default=f"ETF_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            dest="filename",
            help="Filename of the excel ETF report",
        )
        parser.add_argument(
            "--folder",
            default=os.path.dirname(os.path.abspath(__file__)).replace(
                "gamestonk_terminal", "exports"
            ),
            dest="folder",
            help="Folder where the excel ETF report will be saved",
        )
        if other_args and "-" not in other_args[0][0]:
            other_args.insert(0, "-e")
        ns_parser = parse_known_args_and_warn(parser, other_args)
        if ns_parser:
            if self.etf_name:
                create_ETF_report(
                    ns_parser.names if ns_parser.names else [self.etf_name],
                    filename=ns_parser.filename,
                    folder=ns_parser.folder,
                )
                print(
                    f"Created ETF report as {ns_parser.filename} in folder {ns_parser.folder} \n"
                )

    def call_weights(self, other_args: List[str]):
        """Process weights command"""
        parser = argparse.ArgumentParser(
            add_help=False,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog="weights",
            description="Look at ETF sector holdings",
        )
        parser.add_argument(
            "-m",
            "--min",
            type=check_non_negative_float,
            dest="min",
            help="Minimum positive float to display sector",
            default=5,
        )
        parser.add_argument(
            "--raw",
            action="store_true",
            dest="raw",
            help="Only output raw data",
        )
        if other_args and "-" not in other_args[0][0]:
            other_args.insert(0, "-l")

        ns_parser = parse_known_args_and_warn(
            parser, other_args, export_allowed=EXPORT_BOTH_RAW_DATA_AND_FIGURES
        )
        if ns_parser:
            yfinance_view.display_etf_weightings(
                name=self.etf_name,
                raw=ns_parser.raw,
                min_pct_to_display=ns_parser.min,
                export=ns_parser.export,
            )

    def call_summary(self, other_args: List[str]):
        """Process summary command"""
        parser = argparse.ArgumentParser(
            add_help=False,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog="summary",
            description="Print ETF description summary",
        )
        ns_parser = parse_known_args_and_warn(
            parser,
            other_args,
        )
        if ns_parser:
            yfinance_view.display_etf_description(
                name=self.etf_name,
            )

    def call_ta(self, _):
        """Process ta command"""
        if self.etf_name:
            self.queue = ta_controller.TechnicalAnalysisController(
                self.etf_name, self.etf_data.index[0], self.etf_data, self.queue
            ).menu()
        else:
            print("Use 'load <ticker>' prior to this command!", "\n")

    def call_pred(self, _):
        """Process pred command"""
        if gtff.ENABLE_PREDICT:
            if self.etf_name:
                try:
                    from gamestonk_terminal.etf.prediction_techniques import (
                        pred_controller,
                    )

                    self.queue = pred_controller.PredictionTechniquesController(
                        self.etf_name,
                        self.etf_data.index[0],
                        "1440min",
                        self.etf_data,
                        self.queue,
                    ).menu()
                except ModuleNotFoundError as e:
                    print(
                        "One of the optional packages seems to be missing: ",
                        e,
                        "\n",
                    )
            else:
                print("Use 'load <ticker>' prior to this command!", "\n")
        else:
            print(
                "Predict is disabled. Check ENABLE_PREDICT flag on feature_flags.py",
                "\n",
            )

    def call_ca(self, _):
        """Process ca command"""
        if len(self.etf_holdings) > 0:
            self.queue = ca_controller.ComparisonAnalysisController(
                self.etf_holdings, self.queue
            ).menu(custom_path_menu_above="/stocks/")

    def call_scr(self, _):
        """Process scr command"""
        self.queue = screener_controller.ScreenerController(self.queue).menu()

    def call_disc(self, _):
        """Process disc command"""
        self.queue = disc_controller.DiscoveryController(self.queue).menu()

    def call_compare(self, other_args):
        """Process compare command"""
        parser = argparse.ArgumentParser(
            add_help=False,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            prog="compare",
            description="Compare selected ETFs [Source: StockAnalysis]",
        )
        parser.add_argument(
            "-e",
            "--etfs",
            type=str,
            dest="names",
            help="Symbols to compare",
            required="-h" not in other_args,
        )

        if other_args and "-" not in other_args[0][0]:
            other_args.insert(0, "-e")

        ns_parser = parse_known_args_and_warn(
            parser, other_args, export_allowed=EXPORT_ONLY_RAW_DATA_ALLOWED
        )
        if ns_parser:
            etf_list = ns_parser.names.upper().split(",")
            stockanalysis_view.view_comparisons(etf_list, export=ns_parser.export)