# First the monkeypatch stuff

import sys
import os
import pkg_resources
from pip.exceptions import InstallationError
from pip.log import logger
from pip.backwardcompat import HTTPError
from pip.index import Link
from pip.req import InstallRequirement
from pip.util import display_path
from pip.download import url_to_path

def prettify(req):
    req = '\033[31m%s\033[0m' % req
    req = req.replace(' (from', ' \033[33m(from')
    return req

investigate = []

# This is a copy of pip.req's prepare_files, but with the line "FIXME: check
# for conflict" replaced with some code that - checks for conflicts.
def prepare_files(self, finder, force_root_egg_info=False, bundle=False):
    """Prepare process. Create temp directories, download and/or unpack files."""
    unnamed = list(self.unnamed_requirements)
    reqs = list(self.requirements.values())
    while reqs or unnamed:
        if unnamed:
            req_to_install = unnamed.pop(0)
        else:
            req_to_install = reqs.pop(0)
        install = True
        best_installed = False
        if not self.ignore_installed and not req_to_install.editable:
            req_to_install.check_if_exists()
            if req_to_install.satisfied_by:
                if self.upgrade:
                    if not self.force_reinstall:
                        try:
                            url = finder.find_requirement(
                                req_to_install, self.upgrade)
                        except BestVersionAlreadyInstalled:
                            best_installed = True
                            install = False
                        else:
                            # Avoid the need to call find_requirement again
                            req_to_install.url = url.url

                    if not best_installed:
                        req_to_install.conflicts_with = req_to_install.satisfied_by
                        req_to_install.satisfied_by = None
                else:
                    install = False
            if req_to_install.satisfied_by:
                if best_installed:
                    logger.notify('Requirement already up-to-date: %s'
                                  % req_to_install)
                else:
                    logger.notify('Requirement already satisfied '
                                  '(use --upgrade to upgrade): %s'
                                  % req_to_install)
        if req_to_install.editable:
            logger.notify('Obtaining %s' % req_to_install)
        elif install:
            if req_to_install.url and req_to_install.url.lower().startswith('file:'):
                logger.notify('Unpacking %s' % display_path(url_to_path(req_to_install.url)))
            else:
                logger.notify('Downloading/unpacking %s' % req_to_install)
        logger.indent += 2
        try:
            is_bundle = False
            if req_to_install.editable:
                if req_to_install.source_dir is None:
                    location = req_to_install.build_location(self.src_dir)
                    req_to_install.source_dir = location
                else:
                    location = req_to_install.source_dir
                if not os.path.exists(self.build_dir):
                    _make_build_dir(self.build_dir)
                req_to_install.update_editable(not self.is_download)
                if self.is_download:
                    req_to_install.run_egg_info()
                    req_to_install.archive(self.download_dir)
                else:
                    req_to_install.run_egg_info()
            elif install:
                ##@@ if filesystem packages are not marked
                ##editable in a req, a non deterministic error
                ##occurs when the script attempts to unpack the
                ##build directory

                location = req_to_install.build_location(self.build_dir, not self.is_download)
                ## FIXME: is the existance of the checkout good enough to use it?  I don't think so.
                unpack = True
                url = None
                if not os.path.exists(os.path.join(location, 'setup.py')):
                    ## FIXME: this won't upgrade when there's an existing package unpacked in `location`
                    if req_to_install.url is None:
                        url = finder.find_requirement(req_to_install, upgrade=self.upgrade)
                    else:
                        ## FIXME: should req_to_install.url already be a link?
                        url = Link(req_to_install.url)
                        assert url
                    if url:
                        try:
                            self.unpack_url(url, location, self.is_download)
                        except HTTPError:
                            e = sys.exc_info()[1]
                            logger.fatal('Could not install requirement %s because of error %s'
                                          % (req_to_install, e))
                            raise InstallationError(
                                'Could not install requirement %s because of HTTP error %s for URL %s'
                                % (req_to_install, e, url))
                    else:
                        unpack = False
                if unpack:
                    is_bundle = req_to_install.is_bundle
                    if is_bundle:
                        req_to_install.move_bundle_files(self.build_dir, self.src_dir)
                        for subreq in req_to_install.bundle_requirements():
                            reqs.append(subreq)
                            self.add_requirement(subreq)
                    elif self.is_download:
                        req_to_install.source_dir = location
                        req_to_install.run_egg_info()
                        if url and url.scheme in vcs.all_schemes:
                            req_to_install.archive(self.download_dir)
                    else:
                        req_to_install.source_dir = location
                        req_to_install.run_egg_info()
                        if force_root_egg_info:
                            # We need to run this to make sure that the .egg-info/
                            # directory is created for packing in the bundle
                            req_to_install.run_egg_info(force_root_egg_info=True)
                        req_to_install.assert_source_matches_version()
                        #@@ sketchy way of identifying packages not grabbed from an index
                        if bundle and req_to_install.url:
                            self.copy_to_build_dir(req_to_install)
                            install = False
                    # req_to_install.req is only avail after unpack for URL pkgs
                    # repeat check_if_exists to uninstall-on-upgrade (#14)
                    req_to_install.check_if_exists()
                    if req_to_install.satisfied_by:
                        if self.upgrade or self.ignore_installed:
                            req_to_install.conflicts_with = req_to_install.satisfied_by
                            req_to_install.satisfied_by = None
                        else:
                            install = False
            if not is_bundle:
                ## FIXME: shouldn't be globally added:
                finder.add_dependency_links(req_to_install.dependency_links)
                if (req_to_install.extras):
                    logger.notify("Installing extra requirements: %r" % ','.join(req_to_install.extras))
                if not self.ignore_dependencies:
                    for req in req_to_install.requirements(req_to_install.extras):
                        try:
                            name = pkg_resources.Requirement.parse(req).project_name
                        except ValueError:
                            e = sys.exc_info()[1]
                            ## FIXME: proper warning
                            logger.error('Invalid requirement: %r (%s) in requirement %s' % (req, e, req_to_install))
                            continue
                        subreq = InstallRequirement(req, req_to_install)
                        if self.has_requirement(name):
                            investigate.append([ self.get_requirement(name), subreq ])
                            continue
                        reqs.append(subreq)
                        self.add_requirement(subreq)
                if req_to_install.name not in self.requirements:
                    self.requirements[req_to_install.name] = req_to_install
                if self.is_download:
                    self.reqs_to_cleanup.append(req_to_install)
            else:
                self.reqs_to_cleanup.append(req_to_install)

            if install:
                self.successfully_downloaded.append(req_to_install)
                if bundle and (req_to_install.url and req_to_install.url.startswith('file:///')):
                    self.copy_to_build_dir(req_to_install)
        finally:
            logger.indent -= 2

# ---

import optparse

from pip.index import PackageFinder
from pip.req import RequirementSet, parse_requirements
from pip.locations import build_prefix, src_prefix

try:
    # Set up the version control backends
    from pip import version_control
    version_control()
except:
    # Recent versions of pip don't need this
    pass

# Logging
parser = optparse.OptionParser(usage='%prog [--verbose] <requirements file>')
parser.add_option('-v', '--verbose', action='store_true', dest='verbose')
options, args = parser.parse_args()
level = 1 if options.verbose else 0
level = logger.level_for_integer(4-level)
logger.consumers.extend([(level, sys.stdout)])

if not len(args):
    parser.print_help()
    sys.exit()

# Monkey patch our above redefined function
RequirementSet.prepare_files = prepare_files
# Bits of what pip install --no-install does, as minimal as we can
requirement_set = RequirementSet(build_dir=build_prefix, src_dir=src_prefix, download_dir=None, download_cache=None, upgrade=None, ignore_installed=None, ignore_dependencies=False, force_reinstall=None)

class Opt:
    skip_requirements_regex = None
for req in parse_requirements(args[0], options=Opt):
    requirement_set.add_requirement(req)

finder = PackageFinder(find_links=[], index_urls=['http://pypi.python.org/simple/'], use_mirrors=True, mirrors=[])
requirement_set.prepare_files(finder)

for first, later in investigate:
    later.check_if_exists()
    if later.satisfied_by:
        pass # print 'already satisfied by %s' % (later.satisfied_by)
    elif later.conflicts_with:
        print '%s conflicts with installed \033[31m%s\033[0m' % (prettify(later), later.conflicts_with)
    else:
        if first.installed_version not in later.req:
            print '%s, but pip will install version \033[31m%s\033[0m from \033[33m%s\033[0m' % (prettify(later), first.installed_version, first)

