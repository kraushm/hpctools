# Copyright 2019-2020 Swiss National Supercomputing Centre (CSCS/ETH Zurich)
# HPCTools Project Developers. See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import os
import sys
import reframe as rfm
import reframe.utility.sanity as sn
from reframe.core.backends import getlauncher
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),
                '../common')))  # noqa: E402
import sphexa.sanity as sphs


# NOTE: jenkins restricted to 1 cnode
mpi_tasks = [24, 96]  # [24, 48, 96, 192]
cubeside_dict = {1: 30, 12: 78, 24: 100, 48: 125, 96: 157, 192: 198}
steps_dict = {1: 1, 12: 1, 24: 1, 48: 1, 96: 1, 192: 1}  # use same step


# {{{ class SphExa_Container_Base_Check
class SphExa_Container_Base_Check(rfm.RegressionTest):
    # {{{
    '''
    2 parameters can be set for simulation:

    :arg mpi_task: number of mpi tasks; the size of the cube in the 3D
         square patch test is set with a dictionary depending on mpi_task,
         but cubesize could also be on the list of parameters,
    :arg step: number of simulation steps.

    Dependencies are:
        - compute: inputs (mpi_task, step) ---srun---> *job.out
        - postprocess logs: inputs (*job.out) ---x---> termgraph.in
        - plot data: inputs (termgraph.in) ---termgraph.py---> termgraph.rpt
    '''
    # }}}

    def __init__(self, mpi_task, step, container_d):
        # {{{ pe
        self.descr = 'Tool validation'
        self.valid_prog_environs = ['builtin', 'PrgEnv-gnu', 'PrgEnv-intel',
                                    'PrgEnv-pgi', 'PrgEnv-cray']
        # self.sourcesdir = None
        # self.valid_systems = ['daint:gpu', 'dom:gpu']
        self.valid_systems = ['*']
        self.maintainers = ['JG']
        self.tags = {'sph', 'hpctools', 'cpu', 'container'}
        # }}}

        # {{{ compile
        self.testname = 'sqpatch'
        self.modules = [container_d['modulefiles']]
        self.build_system = 'SingleSource'
        self.sourcepath = f'{self.testname}.cpp'
        self.executable = f'./{self.testname}.exe'
        self.native_executable = self.executable
        # unload xalt to avoid _buffer_decode error and,
        # unload container to build native app:
        prebuild_cmds = [
            'module rm xalt', f"module rm {container_d['modulefiles']}",
            'module load cray-mpich'
        ]
        self.prebuild_cmds = prebuild_cmds
        self.postbuild_cmds = [
            f"mv {container_d['runtime']} {self.native_executable}"]
        self.prgenv_flags = {
            'PrgEnv-gnu': ['-I.', '-I./include', '-std=c++14', '-g', '-O2',
                           '-DUSE_MPI', '-DNDEBUG'],
            'PrgEnv-intel': ['-I.', '-I./include', '-std=c++14', '-g', '-O2',
                             '-DUSE_MPI', '-DNDEBUG'],
            'PrgEnv-cray': ['-I.', '-I./include', '-std=c++17', '-g', '-O2',
                            '-DUSE_MPI', '-DNDEBUG'],
            'PrgEnv-pgi': ['-I.', '-I./include', '-std=c++14', '-g', '-O2',
                           '-DUSE_MPI', '-DNDEBUG'],
        }
        # }}}

        # {{{ run
        ompthread = 1
        self.num_tasks = mpi_task
        self.cubeside = cubeside_dict[mpi_task]
        self.steps = steps_dict[mpi_task]
        self.num_tasks_per_node = 24
        self.num_tasks_per_core = 2
        self.use_multithreading = True
        self.num_cpus_per_task = ompthread
        self.exclusive = True
        self.time_limit = '10m'
        self.variables['OMP_NUM_THREADS'] = str(self.num_cpus_per_task)
        # Note: do not use "container_platform_options = 'run'"
        container_platform_options = container_d['options']
        container_platform_projectdir = container_d['projectdir']
        container_platform_repo = container_d['scratch']
        container_platform_image = f"{container_d['image']}"
        container_platform_variables = container_d['variables']
        container_platform_executable = container_d['executable']
        executable_arguments = container_d['executable_opts']
        self.prerun_cmds += [
            'module rm xalt',
            'module list -t',
            f'## rsync -av {container_platform_projectdir} '
            f'{container_platform_repo}',
        ]
        self.executable = container_d['runtime']
        self.executable_opts = [
            container_platform_options, container_platform_image,
            'bash', '-c', f"'{container_platform_variables} "
            f"{container_platform_executable} {executable_arguments}'", '2>&1']
        # }}}

        # {{{ sanity
        # self.sanity_patterns_l = [
        self.sanity_patterns = \
            sn.assert_found(r'Total time for iteration\(0\)', self.stdout)
        # self.sanity_patterns = sn.all(self.sanity_patterns_l)
        # }}}

        # {{{ performance
        # {{{ internal timers
        self.prerun_cmds += ['echo starttime=`date +%s`']
        self.postrun_cmds += ['echo stoptime=`date +%s`']
        # }}}

        # {{{ perf_patterns:
        # self.perf_patterns = sn.evaluate(sphs.basic_perf_patterns(self))
        # }}}

        # {{{ reference:
        # self.reference = sn.evaluate(sphs.basic_reference_scoped_d(self))
        # self.reference = sn.evaluate(sphsintel.vtune_tool_reference(self))
        # }}}
        # }}}

    # {{{ hooks
    @rfm.run_before('compile')
    def set_compiler_flags(self):
        self.build_system.cxxflags = \
            self.prgenv_flags[self.current_environ.name]
    # }}}
# }}}


# {{{ class MPI_Compute_Singularity_Test:
@rfm.parameterized_test(*[[mpi_task] for mpi_task in mpi_tasks])
class MPI_Compute_Singularity_Test(SphExa_Container_Base_Check):
    # {{{
    '''
    This class run the executable with Singularity
    (and natively too for comparison)
    '''
    # }}}

    def __init__(self, mpi_task):
        # share args with TestBase class
        step = steps_dict[mpi_task]
        cubeside = cubeside_dict[mpi_task]
        self.name = f'compute_singularity_{mpi_task}mpi_{step}steps'
        nativejob_stdout = 'rfm_' + \
            self.name.replace("singularity", "native") + '_job.out'
        container_d = {
            # for now: module use ~/easybuild/dom/haswell/modules/all
            'modulefiles': 'singularity/3.5.3-dom',
            'runtime': 'singularity',
            'options': 'exec',
            'projectdir': '/project/csstaff/piccinal/CONTAINERS/sph',
            'scratch': '$SCRATCH/CONTAINERS/sph',
            'image':
                '$SCRATCH/CONTAINERS/sph/ub1804_cuda102_mpich314_gnu8+sph.sif',
            'variables': '',
            'mount': '',  # '-B"/x:/x"'
            'executable': '/home/bin/gnu8/mpi+omp.app',
            'executable_opts': f'-n {cubeside} -s {step}'
        }
        self.variables['SINGULARITYENV_LD_LIBRARY_PATH'] = \
            '/opt/gcc/8.3.0/snos/lib64:$SINGULARITYENV_LD_LIBRARY_PATH'
        super().__init__(mpi_task, step, container_d)
        # {{{ --- run the native executable too:
        nativejob_launcher = 'srun'
        # TODO: self.nativejob_launcher = self.current_partition.launcher
        postrun_cmds = [
            # native app:
            # f'ldd {self.native_executable}',
            '# --- native run (no container) ---',
            f'echo starttime=`date +%s` > {nativejob_stdout} 2>&1',
            f"{nativejob_launcher} {self.native_executable} "
            f"{container_d['executable_opts']} >> {nativejob_stdout} 2>&1",
            f'echo stoptime=`date +%s` >> {nativejob_stdout} 2>&1',
        ]
        self.postrun_cmds.extend(postrun_cmds)
        # }}}
        self.rpt_dep = None
# }}}


# {{{ class MPI_Compute_Sarus_Test:
@rfm.parameterized_test(*[[mpi_task] for mpi_task in mpi_tasks])
class MPI_Compute_Sarus_Test(SphExa_Container_Base_Check):
    # {{{
    '''
    This class run the executable with Sarus
    '''
    # }}}

    def __init__(self, mpi_task):
        # share args with TestBase class
        step = steps_dict[mpi_task]
        cubeside = cubeside_dict[mpi_task]
        self.name = f'compute_sarus_{mpi_task}mpi_{step}steps'
        container_d = {
            'modulefiles': 'sarus/1.1.0',
            'runtime': 'sarus',
            'options': 'run --mpi',
            'projectdir': '/project/csstaff/piccinal/CONTAINERS/sph',
            'scratch': '$SCRATCH/CONTAINERS/sph',
            'localimage': 'ub1804_cuda102_mpich314_gnu8+sph.tar',
            # 'scratch': '',
            'image': 'load/library/ub1804_cuda102_mpich314_gnu8:sph',
            'variables': '',
            'mount': '',
            'executable': '/home/bin/gnu8/mpi+omp.app',
            'executable_opts': f'-n {cubeside} -s {step}'
        }
        self.prerun_cmds = [
            # sarus rmi ...
            f"{container_d['runtime']} load "
            f"{container_d['scratch']}/{container_d['localimage']} "
            f"{container_d['image']}",
            f"{container_d['runtime']} images",
        ]
        super().__init__(mpi_task, step, container_d)
        self.rpt_dep = None
# }}}


# {{{ class MPI_Collect_Logs_Test:
@rfm.simple_test
class MPI_Collect_Logs_Test(rfm.RunOnlyRegressionTest):
    def __init__(self):
        self.name = 'postproc_containers'
        self.valid_systems = ['*']
        self.valid_prog_environs = ['*']
        self.sourcesdir = None
        self.modules = []
        self.num_tasks_per_node = 1
        self.num_tasks = 1
        self.executable = 'echo "collecting jobs stdout"'
        self.sanity_patterns = sn.assert_not_found(r'error', self.stdout)
        # --- construct list of dependencies from container1 (from testname):
        self.testnames_singularity = \
            [f'compute_singularity_{mpi_task}mpi_{step}steps'
             for step in set(steps_dict.values()) for mpi_task in mpi_tasks]
        # print('self.testnames_singularity=', self.testnames_singularity)
        for test in self.testnames_singularity:
            self.depends_on(test)

        # --- construct list of dependencies from container2 (from testname):
        self.testnames_sarus = \
            [f'compute_sarus_{mpi_task}mpi_{step}steps'
             for step in set(steps_dict.values()) for mpi_task in mpi_tasks]
        # print('self.testnames_sarus=', self.testnames_sarus)
        for test in self.testnames_sarus:
            self.depends_on(test)

    @rfm.require_deps
    def collect_logs(self):
        """
        cp all the stdout logs from the compute jobs for postprocessing
        """
        job_out = '*_job.out'
        # --- singularity test logs:
        for test_index in range(len(self.testnames_singularity)):
            stagedir = \
                self.getdep(self.testnames_singularity[test_index]).stagedir

            self.postrun_cmds.append(f'cp {stagedir}/{job_out} .')
        # --- sarus test logs:
        for test_index in range(len(self.testnames_sarus)):
            stagedir = self.getdep(self.testnames_sarus[test_index]).stagedir
            self.postrun_cmds.append(f'cp {stagedir}/{job_out} .')

    @rfm.run_after('run')
    def extract_data(self):
        """
        returns the time taken by srun by reading timings of all the compute
        jobs (linux date start/stop command) and write results in timings.rpt
        """
        ftgin = open(os.path.join(self.stagedir, 'timings.rpt'), "w")
        # termgraph header:
        # ftgin.write('# Elapsed_time (seconds) = f(mpi_tasks)\n')
        ftgin.write('@ native,singularity,sarus\n')
        # title of column1 not needed i.e this is wrong: ('@ mpi,t1,t2\n')
        job_out = 'job.out'
        # TODO: reuse self.testnames_native here
        # for step in steps:
        for step in set(steps_dict.values()):
            for mpi_task in mpi_tasks:
                # native (i.e no container) -> res_native
                # testname = self.nativejob_stdout
                testname = f'compute_native_{mpi_task}mpi_{step}steps'
                self.rpt_dep = os.path.join(self.stagedir,
                                            f'rfm_{testname}_{job_out}')
                # self.rpt_dep = os.path.join(self.stagedir, nativejob_stdout)
                res_native = sn.evaluate(sphs.elapsed_time_from_date(self))
                # rfm_postproc_containers_job.out: No such file or directory
                # --> update sphs.elapsed_time_from_date with self.rpt
                # --- singularity -> res_singularity
                testname = f'compute_singularity_{mpi_task}mpi_{step}steps'
                self.rpt_dep = os.path.join(self.stagedir,
                                            f'rfm_{testname}_{job_out}')
                res_singularity = \
                    sn.evaluate(sphs.elapsed_time_from_date(self))
                # --- sarus -> res_sarus
                testname = f'compute_sarus_{mpi_task}mpi_{step}steps'
                self.rpt_dep = os.path.join(self.stagedir,
                                            f'rfm_{testname}_{job_out}')
                res_sarus = sn.evaluate(sphs.elapsed_time_from_date(self))
                # --- termgraph data:
                ftgin.write(f'{mpi_task},{res_native},{res_singularity},'
                            f'{res_sarus}\n')
        ftgin.close()
# }}}


# {{{ class MPI_PostprocTest:
@rfm.simple_test
class MPI_Plot_Test(rfm.RunOnlyRegressionTest):
    def __init__(self):
        self.name = 'performance_containers'
        self.sourcesdir = 'src/scripts'
        # This test will be skipped if --system does not match:
        self.valid_systems = ['dom:mc', 'dom:gpu']
        self.valid_prog_environs = ['*']
        self.modules = ['termgraph/0.4.2-python3']
        self.depends_on('postproc_containers')
        self.executable = 'python3'
        # TODO: avg time per step
        self.sanity_patterns = \
            sn.assert_not_found(r'ordinal not in range', self.stderr)

    @rfm.require_deps
    def plot_logs(self):
        stagedir = self.getdep('postproc_containers').stagedir
        rpt = os.path.join(stagedir, 'timings.rpt')
        tgraph = os.path.join(self.stagedir, 'termgraph_cscs.py')
        self.executable_opts = [
            f'{tgraph}', f'{rpt}', '--color', '{green,yellow,red}', '--suffix',
            's', '--title', '"Elapsed time (seconds)"']
        self.postrun_cmds = [f'# cat termgraph.rpt']

# }}}
