/* This file is part of Netsukuku
 * (c) Copyright 2005 Andrea Lo Pumo aka AlpT <alpt@freaknet.org>
 *
 * This source code is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as published
 * by the Free Software Foundation; either version 2 of the License,
 * or (at your option) any later version.
 *
 * This source code is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
 * Please refer to the GNU Public License for more details.
 *
 * You should have received a copy of the GNU Public License along with
 * this source code; if not, write to:
 * Free Software Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 *
 * --
 * rehook.c: 
 * This code manages the rehook of gnodes, the challenges that must be solved
 * and generated in order to prove the number of nodes present in a gnode.
 */

#include "includes.h"

#include "misc.h"
#include "libnetlink.h"
#include "ll_map.h"
#include "inet.h"
#include "if.h"
#include "krnl_route.h"
#include "endianness.h"
#include "bmap.h"
#include "route.h"
#include "request.h"
#include "pkts.h"
#include "tracer.h"
#include "qspn.h"
#include "andna.h"
#include "hook.h"
#include "rehook.h"
#include "radar.h"
#include "netsukuku.h"
#include "xmalloc.h"
#include "log.h"
#include "misc.h"

/*
 * rehook_argv: argv for the new_rehook_thread thread
 */
struct rehook_argv {
		int gnode;
		int level;
		int gnode_count;
};

pthread_attr_t new_rehook_thread_attr;

void rehook_init(void)
{
	total_rehooks=0;
	last_instance_rehook=0;
	rehook_mutex=0;

	pthread_attr_init(&new_rehook_thread_attr);
	pthread_attr_setdetachstate(&new_rehook_thread_attr, PTHREAD_CREATE_DETACHED);	 
}

int send_challenge(int gnode, int level, int gnode_count)
{
	/* TODO ^_^ */
	
	return 0;
}


/*
 * update_rehook_time: updates the rehook_time counter. If the limits are
 * reached -1 is returned and nothing is changed, otherwise 0 is the returned
 * value. (See rehook.h for more info on the limits).
 */
int update_rehook_time(int level)
{
	time_t cur_t, sec_elapsed;

	cur_t=time(0);
	sec_elapsed=(cur_t - last_instance_rehook);
	
	if(total_rehooks && sec_elapsed > REHOOK_INSTANCE_TIME(level)) {
		/* 
		 * REHOOK_INSTANCE_TIME expired: we cannot take no more rehooks
		 * in this instance. 
		 */
		
		if(sec_elapsed > REHOOK_WAIT_TIME(level))
			/* REHOOK_WAIT_TIME expired: a new instance begins */
			total_rehooks=0;
		else
			return -1;
	}
	
	if(total_rehooks > REHOOK_PER_INSTANCE)
		/* Too many rehooks in this instance */
		return -1;
	
	if(!total_rehooks)
		last_instance_rehook=cur_t;
	total_rehooks++;

	return 0;
}

/*
 * new_rehook_thread: a thread for each rehook() is necessary because the
 * rehook has to run without stopping the calling thread.
 */
void *new_rehook_thread(void *r)
{
	struct rehook_argv *rargv=(struct rehook_argv *)r;
	ext_rnode_cache *erc;
	
	/*
	 * Send a new challenge if `CHALLENGE_THRESHOLD' was exceeded 
	 */
	if(rargv->level && rargv->gnode_count >= CHALLENGE_THRESHOLD)
		if(send_challenge(rargv->gnode, rargv->level, 
					rargv->gnode_count))
			/* Challenge failed, do not rehook */
			goto finish;

	/* TODO:
	wait_rnodes_before_hooking();
	*/
	
	/*
	 * Rehook now
	 */
	rehook();

	if(level) {
		/* Mark all the gnodes we border on as HOOKED, in this way
		 * we won't try to rehook each time */
		erc=me.cur_erc;
		list_for(erc) {	
			if(!p->e)
				continue;
			if(erc->quadg.gnode[_EL(rargv->level)])
				erc->quadg.gnode[_EL(rargv->level)]->flags|=GMAP_HGNODE;
		}
	}

finish:	
	xfree(rargv);
	rehook_mutex=0;	
	return 0;
}

/*
 * new_rehook: takes in exam the `gnode' composed by `gnode_count'# nodes, which
 * is at level `level'.
 * When `level' is 0, `gnode' is a node and gnode_count isn't considered.
 */
void new_rehook(int gnode, int level, int gnode_count)
{
	struct rehook_argv *rargv;
	pthread_t thread;

	if(!level && gnode != me.cur_quadg.gid[level])
		/* We rehook at level 0 only if we have the same gid of
		 * another node, so in this case we don't have to rehook */
		return;
	else if(level) {
		if(gnode_count < qspn_gnode_count[_EL(level)])
			/* We have more nodes, we don't have to rehook! */
			return;
		else if(gnode_count == qspn_gnode_count[_EL(level)] &&
				gnode < me.cur_quadg.gid[level])
			/* We have the same number of nodes, but `gnode' has a
			 * gid id smaller than our, so it must rehook, not us */
			return;
	} 
	
	/*
	 * Update the rehook time and let's see if we can take this new rehook
	 */
	if(update_rehook_time(level))
		return;

	/*
	 * TODO: CONTINUE HERE
	 * check that `gnode' isn't marked as HOOKED, otherwise return.
	 */
	
	if(rehook_mutex)
		return;
	rehook_mutex=1;

	rargv = xmalloc(sizeof(struct rehook_argv));
	rargv->gnode	   = gnode;
	rargv->level	   = level;
	rargv->gnode_count = gnode_count;
	pthread_create(&thread, &new_rehook_thread_attr, new_rehook_thread, 
			(void *)&rargv);
}

/*
 * rehook: resets all the global variables set during the last hook/rehook,
 * and launches the netsukuku_hook() again. All the previous map will be lost
 * if not saved, the IP will also change. 
 * During the rehook, the radar_daemon and andna_maintain_hnames_active() are
 * stopped.
 * After the rehook, the andna_hook will be launched and the stopped daemon
 * reactivated.
 */
int rehook(void)
{
	int ret=0;

	/* Stop the radar_daemon */
	radar_daemon_ctl=0;

	/* Wait the end of the current radar */
	radar_wait_new_scan();

	/* Mark ourself as hooking, this will stop
	 * andna_maintain_hnames_active() daemon too. */
	me.cur_node->flags|=MAP_HNODE;

	/* Reset */
	rnl_reset(&rlist, &rlist_counter);
	e_rnode_free(&me.cur_erc, &me.cur_erc_counter);
	qspn_reset(GET_LEVELS(my_family));

	/* Andna reset */
	andna_cache_destroy();
	counter_c_destroy();
	rh_cache_flush();
	
	/* Clear the uptime */
	me.uptime=time(0);

	/*
	 * * *  REHOOK!  * * *
	 */
	netsukuku_hook();
	andna_hook(0);

	/* Update our hostnames */
	andna_update_hnames(0);

	return ret;
}
