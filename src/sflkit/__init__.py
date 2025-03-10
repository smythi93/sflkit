from os import PathLike
from pathlib import Path

from sflkit.analysis.analyzer import Analyzer
from sflkit.config import Config, parse_config
from sflkit.instrumentation.dir_instrumentation import DirInstrumentation


def instrument_config(conf: Config):
    instrumentation = DirInstrumentation(
        conf.visitor, conf.mapping.path, test_visitor=conf.test_visitor
    )
    instrumentation.instrument(
        conf.target_path,
        conf.instrument_working,
        suffixes=conf.language.suffixes,
        includes=conf.instrument_include,
        excludes=conf.instrument_exclude,
        tests=conf.instrument_test,
        test_files=conf.instrument_test_files,
    )
    instrumentation.dump_events(conf)


def instrument(config_path: PathLike):
    conf = parse_config(config_path)
    instrument_config(conf)


def run_config(conf: Config, output: PathLike = None):
    runner = conf.runner
    if runner is None:
        raise ValueError("No runner defined")
    runner = runner.runner
    if output is None:
        output = (Path.cwd() / "events").absolute()
    else:
        output = Path(output)
    runner.run(conf.instrument_working, output)


def run(config_path: PathLike, output: PathLike = None):
    conf = parse_config(config_path)
    run_config(conf, output)


def analyze_config(conf: Config, analysis_dump: PathLike = None):
    analyzer = Analyzer(conf.failing, conf.passing, conf.factory)
    analyzer.analyze()
    if analysis_dump:
        analyzer.dump(analysis_dump)
    results = dict()
    for analysis_type in conf.predicates:
        results[analysis_type.name] = dict()
        for metric in conf.metrics:
            try:
                results[analysis_type.name][
                    metric.__name__
                ] = analyzer.get_sorted_suggestions(
                    conf.target_path, metric, analysis_type
                )
            except (AttributeError, ValueError, TypeError) as e:
                raise e
    return results


def analyze(config_path: PathLike, analysis_dump: PathLike = None):
    conf = parse_config(config_path)
    return analyze_config(conf, analysis_dump)


__all__ = [
    "analysis",
    "instrument",
    "language",
    "model",
    "runners",
    "config",
    "instrument",
    "instrument_config",
    "analyze",
    "analyze_config",
    "Analyzer",
    "Config",
]
